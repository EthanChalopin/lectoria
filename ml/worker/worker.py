import json
import signal
import time
from datetime import datetime, timezone

from ml.worker.aws_clients import AwsClients
from ml.worker.config import INFERENCE_QUEUE_URL
from ml.worker.logging_utils import LOGGER, log_event
from ml.worker.message_schema import JobMessage
from ml.worker.service import WorkerService


STOP = False


def _handle_stop(signum, frame):
    del signum, frame
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)


def main_loop():
    clients = AwsClients()
    service = WorkerService(
        sqs_client=clients.sqs,
        s3_client=clients.s3,
        stories_table=clients.stories_table,
    )

    log_event("info", "worker_start", component="bookgen-ml-worker", mode="fake_sdxl")

    empty_streak = 0
    base_sleep = 0.5
    max_sleep = 10.0

    while not STOP:
        try:
            messages = service.receive_messages()
        except Exception as exc:
            LOGGER.exception(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "level": "error",
                        "message": "sqs_receive_error",
                        "error": str(exc),
                    },
                    ensure_ascii=False,
                )
            )
            time.sleep(2)
            continue

        if not messages:
            empty_streak += 1
            sleep_s = min(max_sleep, base_sleep * (2 ** min(empty_streak, 6)))
            time.sleep(sleep_s)
            continue

        empty_streak = 0

        for msg in messages:
            receipt_handle = msg["ReceiptHandle"]
            try:
                service.process_message(msg)
                clients.sqs.delete_message(
                    QueueUrl=INFERENCE_QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                )
            except Exception as exc:
                job_id = None
                job_type = None
                try:
                    job = JobMessage.from_sqs_message(msg)
                    job_id = job.job_id
                    job_type = job.job_type
                except Exception:
                    pass
                LOGGER.exception(
                    json.dumps(
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "level": "error",
                            "message": "job_failed_retry",
                            "job_id": job_id,
                            "job_type": job_type,
                            "error": str(exc),
                        },
                        ensure_ascii=False,
                    )
                )

    log_event("info", "worker_stop")


if __name__ == "__main__":
    main_loop()
