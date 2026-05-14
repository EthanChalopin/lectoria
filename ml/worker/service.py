import json
import time

from ml.worker.callbacks import CallbackPublisher
from ml.worker.config import CALLBACKS_QUEUE_URL, INFERENCE_QUEUE_URL
from ml.worker.logging_utils import LOGGER, log_event
from ml.worker.message_schema import JobMessage
from ml.worker.router import get_job_handler
from ml.worker.status_store import StatusStore


class WorkerService:
    def __init__(self, *, sqs_client, s3_client, stories_table, qwen_controller=None):
        self.sqs = sqs_client
        self.s3 = s3_client
        self.status_store = StatusStore(stories_table)
        self.callbacks = CallbackPublisher(self.sqs, CALLBACKS_QUEUE_URL)
        self.qwen_controller = qwen_controller

    def process_message(self, msg: dict) -> None:
        job = JobMessage.from_sqs_message(msg)
        self.status_store.create_job_if_not_exists(job.story_id, job.job_type)
        log_event("info", "job_received", job_id=job.job_id, story_id=job.story_id, job_type=job.job_type)
        self.status_store.update_job_status(job.story_id, "in_progress")

        try:
            handler = get_job_handler(job.job_type)
            result = handler(
                job,
                s3_client=self.s3,
                sqs_client=self.sqs,
                status_store=self.status_store,
                qwen_controller=self.qwen_controller,
            )
            result_attrs = dict(result)
            final_status = result_attrs.pop("status", "completed")
            output_s3_key = result_attrs.get("output_s3_key")
            self.status_store.update_job_status(job.story_id, final_status, extra_attrs=result_attrs)
            if final_status == "completed":
                self.callbacks.publish_completed(
                    job_id=job.job_id,
                    story_id=job.story_id,
                    job_type=job.job_type,
                    output_s3_key=output_s3_key or "",
                )
                log_event(
                    "info",
                    "job_completed",
                    job_id=job.job_id,
                    story_id=job.story_id,
                    job_type=job.job_type,
                    output_s3_key=output_s3_key,
                )
            else:
                log_event(
                    "info",
                    "job_progress",
                    job_id=job.job_id,
                    story_id=job.story_id,
                    job_type=job.job_type,
                    status=final_status,
                    output_s3_key=output_s3_key,
                )
        except Exception as exc:
            LOGGER.exception(
                json.dumps(
                    {
                        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        "level": "error",
                        "message": "job_failed",
                        "job_id": job.job_id,
                        "story_id": job.story_id,
                        "job_type": job.job_type,
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            self.status_store.update_job_status(
                job.story_id,
                "failed",
                extra_attrs={"error": str(exc)},
            )
            self.callbacks.publish_failed(
                job_id=job.job_id,
                story_id=job.story_id,
                job_type=job.job_type,
                error=str(exc),
            )
            raise

    def receive_messages(self) -> list[dict]:
        resp = self.sqs.receive_message(
            QueueUrl=INFERENCE_QUEUE_URL,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=20,
            VisibilityTimeout=300,
        )
        return resp.get("Messages", [])
