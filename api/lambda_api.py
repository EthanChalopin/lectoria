import datetime
import json
import os
import uuid
from decimal import Decimal

import boto3


sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")

INFERENCE_QUEUE_URL = os.environ["INFERENCE_QUEUE_URL"]
DDB_STORIES_TABLE = os.environ["DDB_STORIES_TABLE"]
BUCKET_OUTPUTS = os.environ["BUCKET_OUTPUTS"]
SIGNED_URL_EXPIRES_SECONDS = int(os.environ.get("SIGNED_URL_EXPIRES_SECONDS", "3600"))

table = dynamodb.Table(DDB_STORIES_TABLE)

CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
}


def _response(status_code: int, body: dict | None = None):
    payload = {
        "statusCode": status_code,
        "headers": CORS_HEADERS,
    }
    if body is not None:
        payload["body"] = json.dumps(_json_safe(body))
    return payload


def _json_safe(value):
    if isinstance(value, Decimal):
        if value % 1 == 0:
            return int(value)
        return float(value)
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    return value


def _parse_json_body(event):
    body = event.get("body")
    if body is None:
        raise ValueError("Missing request body")
    if isinstance(body, str):
        return json.loads(body)
    return body


def _create_job(body: dict):
    prompt = body.get("prompt")
    style = body.get("style", "storybook")
    if not prompt:
        return _response(400, {"error": "Missing 'prompt' in body"})

    story_id = str(uuid.uuid4())
    job_id = story_id

    item = {
        "story_id": story_id,
        "job_id": job_id,
        "job_type": "sdxl",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "status": "queued",
        "prompt": prompt,
        "style": style,
    }
    table.put_item(Item=item)

    message_body = {
        "job_id": job_id,
        "story_id": story_id,
        "job_type": "sdxl",
        "payload": {
            "prompt": prompt,
            "style": style,
            **{k: v for k, v in body.items() if k not in {"prompt", "style"}},
        },
    }
    sqs.send_message(
        QueueUrl=INFERENCE_QUEUE_URL,
        MessageBody=json.dumps(message_body),
    )

    return _response(200, {"job_id": job_id, "status": "queued"})


def _create_story_job(body: dict):
    book_prompt = body.get("book_prompt")
    image_style = body.get("image_style", "storybook")
    if not book_prompt:
        return _response(400, {"error": "Missing 'book_prompt' in body"})

    story_id = str(uuid.uuid4())
    job_id = story_id

    item = {
        "story_id": story_id,
        "job_id": job_id,
        "job_type": "story_plan",
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        "status": "queued",
        "prompt": book_prompt,
        "style": image_style,
    }
    table.put_item(Item=item)

    message_body = {
        "job_id": job_id,
        "story_id": story_id,
        "job_type": "story_plan",
        "payload": body,
    }
    sqs.send_message(
        QueueUrl=INFERENCE_QUEUE_URL,
        MessageBody=json.dumps(message_body),
    )

    return _response(200, {"job_id": job_id, "story_id": story_id, "status": "queued"})


def _create_story_images_job(story_id: str, body: dict):
    resp = table.get_item(Key={"story_id": story_id})
    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "Story not found", "story_id": story_id})

    job_id = f"{story_id}:images:{uuid.uuid4()}"
    message_body = {
        "job_id": job_id,
        "story_id": story_id,
        "job_type": "story_render_images",
        "payload": body,
    }
    sqs.send_message(
        QueueUrl=INFERENCE_QUEUE_URL,
        MessageBody=json.dumps(message_body),
    )

    return _response(200, {"job_id": job_id, "story_id": story_id, "status": "queued"})


def _build_signed_output_url(output_s3_key: str | None):
    if not output_s3_key:
        return None
    return s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": BUCKET_OUTPUTS,
            "Key": output_s3_key,
        },
        ExpiresIn=SIGNED_URL_EXPIRES_SECONDS,
    )


def _load_story_manifest(output_s3_key: str | None):
    if not output_s3_key or not output_s3_key.endswith("manifest.json"):
        return None

    try:
        response = s3.get_object(Bucket=BUCKET_OUTPUTS, Key=output_s3_key)
        manifest = json.loads(response["Body"].read().decode("utf-8"))
    except Exception as exc:
        return {"error": f"Failed to load manifest: {exc}"}

    for chapter in manifest.get("chapters", []):
        chapter_s3_key = chapter.get("chapter_s3_key")
        image_s3_key = chapter.get("image_s3_key")
        chapter["chapter_url"] = _build_signed_output_url(chapter_s3_key)
        chapter["image_url"] = _build_signed_output_url(image_s3_key)
    return manifest


def _get_job(job_id: str):
    resp = table.get_item(Key={"story_id": job_id})
    item = resp.get("Item")
    if not item:
        return _response(404, {"error": "Job not found", "job_id": job_id})

    output_s3_key = item.get("output_s3_key")
    body = {
        "job_id": item.get("job_id", item.get("story_id")),
        "story_id": item.get("story_id"),
        "job_type": item.get("job_type"),
        "status": item.get("status"),
        "prompt": item.get("prompt"),
        "style": item.get("style"),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "output_s3_key": output_s3_key,
        "output_url": _build_signed_output_url(output_s3_key),
        "image_url": _build_signed_output_url(output_s3_key),
        "error": item.get("error"),
        "current_stage": item.get("current_stage"),
        "chapters_total": item.get("chapters_total"),
        "chapters_completed": item.get("chapters_completed"),
        "story_title": item.get("story_title"),
        "story_manifest": _load_story_manifest(output_s3_key),
    }
    return _response(200, body)


def lambda_handler(event, context):
    del context
    try:
        method = event.get("requestContext", {}).get("http", {}).get("method", "")
        raw_path = event.get("rawPath", "")
        path_parameters = event.get("pathParameters") or {}
        route_key = event.get("routeKey", "")

        if method == "OPTIONS":
            return _response(204)

        if route_key == "POST /jobs/sdxl" or (method == "POST" and raw_path == "/jobs/sdxl"):
            body = _parse_json_body(event)
            return _create_job(body)

        if route_key == "POST /jobs/story" or (method == "POST" and raw_path == "/jobs/story"):
            body = _parse_json_body(event)
            return _create_story_job(body)

        if route_key == "POST /jobs/{job_id}/images" or (
            method == "POST" and raw_path.startswith("/jobs/") and raw_path.endswith("/images")
        ):
            body = _parse_json_body(event)
            story_id = path_parameters.get("job_id") or raw_path.split("/")[2]
            return _create_story_images_job(story_id, body)

        if route_key == "GET /jobs/{job_id}" or (method == "GET" and raw_path.startswith("/jobs/")):
            job_id = path_parameters.get("job_id") or raw_path.rsplit("/", 1)[-1]
            if not job_id:
                return _response(400, {"error": "Missing job_id"})
            return _get_job(job_id)

        return _response(404, {"error": "Route not found", "route_key": route_key, "path": raw_path})
    except ValueError as exc:
        return _response(400, {"error": str(exc)})
    except Exception as exc:
        print("[LAMBDA] ERROR:", repr(exc))
        return _response(500, {"error": str(exc)})
