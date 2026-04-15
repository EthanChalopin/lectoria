import json
import os
import time
import signal
import logging
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from ml.pipelines.sdxl import generate_fake

AWS_REGION = os.environ.get("AWS_REGION", "eu-west-1")
INFERENCE_QUEUE_URL = os.environ.get(
    "INFERENCE_QUEUE_URL",
    "https://sqs.eu-west-1.amazonaws.com/433101552109/bookgen-inference-queue",
)
CALLBACKS_QUEUE_URL = os.environ.get(
    "CALLBACKS_QUEUE_URL",
    "https://sqs.eu-west-1.amazonaws.com/433101552109/bookgen-callbacks-queue",
)
DDB_TABLE_NAME = os.environ.get("DDB_STORIES_TABLE", "BookgenStories")
BUCKET_OUTPUTS = os.environ.get("BUCKET_OUTPUTS", "bookgen-outputs")

session = boto3.Session(region_name=AWS_REGION)
sqs = session.client("sqs")
dynamodb = session.resource("dynamodb")
s3 = session.client("s3")

stories_table = dynamodb.Table(DDB_TABLE_NAME)

STOP = False


def _handle_stop(signum, frame):
    global STOP
    STOP = True


signal.signal(signal.SIGTERM, _handle_stop)
signal.signal(signal.SIGINT, _handle_stop)

logger = logging.getLogger("bookgen.worker")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_handler)
logger.propagate = False


def log_event(level: str, message: str, **fields):
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        **fields,
    }
    line = json.dumps(payload, ensure_ascii=False)
    if level == "error":
        logger.error(line)
    else:
        logger.info(line)


def create_job_if_not_exists(job_id: str, job_type: str):
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        stories_table.put_item(
            Item={
                "story_id": job_id,
                "job_type": job_type,
                "status": "queued",
                "created_at": now_iso,
                "updated_at": now_iso,
            },
            ConditionExpression="attribute_not_exists(story_id)",
        )
    except ClientError as e:
        # Si l'item existe déjà, on ignore
        if e.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise


def update_job_status(job_id: str, status: str, extra_attrs: dict | None = None):
    now_iso = datetime.now(timezone.utc).isoformat()
    update_expr = ["SET #status = :s", "updated_at = :u"]
    expr_attr_names = {"#status": "status"}
    expr_attr_values = {
        ":s": status,
        ":u": now_iso,
    }

    if extra_attrs:
        for idx, (k, v) in enumerate(extra_attrs.items()):
            placeholder = f":v{idx}"
            name_placeholder = f"#k{idx}"
            update_expr.append(f"{name_placeholder} = {placeholder}")
            expr_attr_names[name_placeholder] = k
            expr_attr_values[placeholder] = v

    stories_table.update_item(
        Key={"story_id": job_id},
        UpdateExpression=", ".join(update_expr),
        ExpressionAttributeNames=expr_attr_names,
        ExpressionAttributeValues=expr_attr_values,
    )


def fake_sdxl_render(prompt: str, style: str, job_id: str) -> str:
    key = f"sdxl/{job_id}.txt"
    content = generate_fake(prompt, style, job_id)
    content["generated_at"] = datetime.now(timezone.utc).isoformat()
    s3.put_object(
        Bucket=BUCKET_OUTPUTS,
        Key=key,
        Body=json.dumps(content).encode("utf-8"),
        ContentType="application/json",
    )
    return key


def generate_output(job_type: str, payload: dict, job_id: str) -> str:
    prompt = payload.get("prompt", "A cute dragon reading a book in a magical library")
    style = payload.get("style", "storybook")

    if job_type == "sdxl":
        return fake_sdxl_render(prompt, style, job_id)

    raise ValueError(f"Unsupported job_type: {job_type}")


def process_message(msg):
    body = json.loads(msg["Body"])
    job_id = body["job_id"]
    job_type = body.get("job_type", "sdxl")
    payload = body.get("payload", {})

    # CRÉE L'ITEM DDB SI ABSENT
    create_job_if_not_exists(job_id, job_type)

    log_event("info", "job_received", job_id=job_id, job_type=job_type)

    update_job_status(job_id, "in_progress")

    try:
        output_key = generate_output(job_type, payload, job_id)

        update_job_status(job_id, "completed", extra_attrs={"output_s3_key": output_key})

        callback_body = {
            "job_id": job_id,
            "status": "completed",
            "job_type": job_type,
            "output_s3_key": output_key,
        }
        sqs.send_message(
            QueueUrl=CALLBACKS_QUEUE_URL,
            MessageBody=json.dumps(callback_body),
        )

        log_event(
            "info",
            "job_completed",
            job_id=job_id,
            job_type=job_type,
            output_s3_key=output_key,
        )

    except Exception as e:
        logger.exception(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "level": "error",
                    "message": "job_failed",
                    "job_id": job_id,
                    "job_type": job_type,
                    "error": str(e),
                },
                ensure_ascii=False,
            )
        )
        update_job_status(job_id, "failed", extra_attrs={"error": str(e)})
        callback_body = {
            "job_id": job_id,
            "status": "failed",
            "job_type": job_type,
            "error": str(e),
        }
        sqs.send_message(
            QueueUrl=CALLBACKS_QUEUE_URL,
            MessageBody=json.dumps(callback_body),
        )
        raise


def main_loop():
    log_event("info", "worker_start", component="bookgen-ml-worker", mode="fake_sdxl")

    empty_streak = 0
    base_sleep = 0.5
    max_sleep = 10.0

    while not STOP:
        try:
            resp = sqs.receive_message(
                QueueUrl=INFERENCE_QUEUE_URL,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,
                VisibilityTimeout=300,
            )
        except Exception as e:
            logger.exception(
                json.dumps(
                    {
                        "ts": datetime.now(timezone.utc).isoformat(),
                        "level": "error",
                        "message": "sqs_receive_error",
                        "error": str(e),
                    },
                    ensure_ascii=False,
                )
            )
            time.sleep(2)
            continue

        messages = resp.get("Messages", [])
        if not messages:
            empty_streak += 1
            sleep_s = min(max_sleep, base_sleep * (2 ** min(empty_streak, 6)))
            time.sleep(sleep_s)
            continue

        empty_streak = 0

        for msg in messages:
            receipt_handle = msg["ReceiptHandle"]
            try:
                process_message(msg)
                sqs.delete_message(
                    QueueUrl=INFERENCE_QUEUE_URL,
                    ReceiptHandle=receipt_handle,
                )
            except Exception as e:
                job_id = None
                job_type = None
                try:
                    body = json.loads(msg.get("Body", "{}"))
                    job_id = body.get("job_id")
                    job_type = body.get("job_type")
                except Exception:
                    pass
                logger.exception(
                    json.dumps(
                        {
                            "ts": datetime.now(timezone.utc).isoformat(),
                            "level": "error",
                            "message": "job_failed_retry",
                            "job_id": job_id,
                            "job_type": job_type,
                            "error": str(e),
                        },
                        ensure_ascii=False,
                    )
                )

    log_event("info", "worker_stop")


if __name__ == "__main__":
    main_loop()
