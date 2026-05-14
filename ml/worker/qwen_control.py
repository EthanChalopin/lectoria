from __future__ import annotations

import time

from ml.worker.config import (
    QWEN_CONTROL_ENABLED,
    QWEN_CONTROL_INSTANCE_NAME,
    QWEN_CONTROL_SERVICE_NAME,
)


class QwenHostController:
    def __init__(
        self,
        *,
        ec2_client,
        ssm_client,
        instance_name: str = QWEN_CONTROL_INSTANCE_NAME,
        service_name: str = QWEN_CONTROL_SERVICE_NAME,
        enabled: bool = QWEN_CONTROL_ENABLED,
    ):
        self.ec2 = ec2_client
        self.ssm = ssm_client
        self.instance_name = instance_name
        self.service_name = service_name
        self.enabled = enabled

    def ensure_started(self, *, wait_until_ready: bool = True) -> None:
        if not self.enabled:
            return
        self._run_shell(f"sudo systemctl start {self.service_name}")
        if wait_until_ready:
            self._run_shell(
                "bash -lc 'for i in $(seq 1 60); do "
                "curl -fsS http://127.0.0.1:8000/health >/dev/null && exit 0; "
                "sleep 5; "
                "done; "
                "exit 1'"
            )

    def stop(self) -> None:
        if not self.enabled:
            return
        self._run_shell(f"sudo systemctl stop {self.service_name}")

    def _find_instance_id(self) -> str:
        response = self.ec2.describe_instances(
            Filters=[
                {"Name": "tag:Name", "Values": [self.instance_name]},
                {"Name": "instance-state-name", "Values": ["running"]},
            ]
        )
        instances = [
            instance["InstanceId"]
            for reservation in response.get("Reservations", [])
            for instance in reservation.get("Instances", [])
        ]
        if not instances:
            raise RuntimeError(f"No running EC2 instance found with Name tag '{self.instance_name}'")
        return instances[0]

    def _run_shell(self, command: str) -> None:
        instance_id = self._find_instance_id()
        response = self.ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [command]},
        )
        command_id = response["Command"]["CommandId"]
        self._wait_for_command(instance_id=instance_id, command_id=command_id)

    def _wait_for_command(self, *, instance_id: str, command_id: str, timeout_s: int = 360) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            invocation = self.ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
            status = invocation["Status"]
            if status == "Success":
                return
            if status in {"Cancelled", "TimedOut", "Failed", "Cancelling"}:
                stderr = invocation.get("StandardErrorContent", "").strip()
                stdout = invocation.get("StandardOutputContent", "").strip()
                details = stderr or stdout or status
                raise RuntimeError(f"Qwen host control failed: {details}")
            time.sleep(5)
        raise RuntimeError("Timed out while waiting for Qwen host control command")
