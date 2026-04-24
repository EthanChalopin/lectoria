import json
from datetime import datetime, timezone

from ml.pipelines.sdxl import generate_fake
from ml.worker.config import BUCKET_OUTPUTS


def handle_sdxl(job, *, s3_client) -> dict:
    prompt = job.payload.get("prompt", "A cute dragon reading a book in a magical library")
    style = job.payload.get("style", "storybook")
    key = f"sdxl/{job.job_id}.txt"

    content = generate_fake(prompt, style, job.job_id)
    content["generated_at"] = datetime.now(timezone.utc).isoformat()

    s3_client.put_object(
        Bucket=BUCKET_OUTPUTS,
        Key=key,
        Body=json.dumps(content).encode("utf-8"),
        ContentType="application/json",
    )
    return {"output_s3_key": key}


def handle_zero123(job, **_kwargs) -> dict:
    num_views = job.payload.get("num_views", 8)
    return {
        "result": "stub_zero123",
        "num_views": num_views,
    }


def handle_lora_train(job, **_kwargs) -> dict:
    return {
        "result": "stub_lora_train",
        "lora_key": job.payload.get("lora_key"),
    }
