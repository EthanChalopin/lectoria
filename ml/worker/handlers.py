from ml.pipelines.sdxl import render_png_bytes
from ml.worker.config import (
    BUCKET_OUTPUTS,
    SDXL_DEFAULT_GUIDANCE_SCALE,
    SDXL_DEFAULT_HEIGHT,
    SDXL_DEFAULT_NEGATIVE_PROMPT,
    SDXL_DEFAULT_STEPS,
    SDXL_DEFAULT_WIDTH,
)


def handle_sdxl(job, *, s3_client) -> dict:
    prompt = job.payload.get("prompt", "A cute dragon reading a book in a magical library")
    style = job.payload.get("style")
    if style:
        prompt = f"{prompt}, {style}"

    negative_prompt = job.payload.get("negative_prompt", SDXL_DEFAULT_NEGATIVE_PROMPT)
    width = int(job.payload.get("width", SDXL_DEFAULT_WIDTH))
    height = int(job.payload.get("height", SDXL_DEFAULT_HEIGHT))
    num_inference_steps = int(job.payload.get("num_inference_steps", SDXL_DEFAULT_STEPS))
    guidance_scale = float(job.payload.get("guidance_scale", SDXL_DEFAULT_GUIDANCE_SCALE))
    seed = job.payload.get("seed")
    seed = int(seed) if seed is not None else None

    key = f"sdxl/{job.job_id}.png"
    image_bytes = render_png_bytes(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        seed=seed,
    )

    s3_client.put_object(
        Bucket=BUCKET_OUTPUTS,
        Key=key,
        Body=image_bytes,
        ContentType="image/png",
    )
    return {
        "output_s3_key": key,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
        "seed": seed,
    }


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
