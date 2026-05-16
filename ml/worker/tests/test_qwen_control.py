import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError

from ml.worker.qwen_control import QwenHostController


class FakeEc2Client:
    def describe_instances(self, Filters):
        del Filters
        return {
            "Reservations": [
                {
                    "Instances": [
                        {
                            "InstanceId": "i-1234567890",
                        }
                    ]
                }
            ]
        }


class FakeSsmClient:
    def __init__(self):
        self.calls = 0

    def send_command(self, **kwargs):
        del kwargs
        return {"Command": {"CommandId": "cmd-123"}}

    def get_command_invocation(self, **kwargs):
        del kwargs
        self.calls += 1
        if self.calls == 1:
            raise ClientError(
                {
                    "Error": {
                        "Code": "InvocationDoesNotExist",
                        "Message": "Invocation not ready yet",
                    }
                },
                "GetCommandInvocation",
            )
        return {"Status": "Success"}


class QwenHostControllerTests(unittest.TestCase):
    @patch("ml.worker.qwen_control.time.sleep", return_value=None)
    def test_wait_for_command_retries_invocation_does_not_exist(self, _mock_sleep):
        controller = QwenHostController(
            ec2_client=FakeEc2Client(),
            ssm_client=FakeSsmClient(),
        )

        controller.ensure_started(wait_until_ready=False)


if __name__ == "__main__":
    unittest.main()
