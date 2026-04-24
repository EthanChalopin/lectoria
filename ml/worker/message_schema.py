import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class JobMessage:
    job_id: str
    story_id: str
    job_type: str
    payload: dict[str, Any]

    @classmethod
    def from_sqs_message(cls, msg: dict[str, Any]) -> "JobMessage":
        try:
            body = json.loads(msg["Body"])
        except KeyError as exc:
            raise ValueError("Missing SQS message body") from exc
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc

        if not isinstance(body, dict):
            raise ValueError("Job body must be an object")

        job_id = body.get("job_id")
        if not job_id or not isinstance(job_id, str):
            raise ValueError("Missing or invalid job_id")

        story_id = body.get("story_id", job_id)
        if not isinstance(story_id, str):
            raise ValueError("Invalid story_id")

        job_type = body.get("job_type", "sdxl")
        if not job_type or not isinstance(job_type, str):
            raise ValueError("Missing or invalid job_type")

        payload = body.get("payload", {})
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            raise ValueError("payload must be an object")

        return cls(
            job_id=job_id,
            story_id=story_id,
            job_type=job_type,
            payload=payload,
        )
