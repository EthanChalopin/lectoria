from __future__ import annotations

from ml.pipelines.qwen_chapters import build_chapter, build_story_plan
from ml.pipelines.sdxl import render_png_bytes, unload_pipeline
from ml.worker.config import (
    BUCKET_OUTPUTS,
    SDXL_DEFAULT_GUIDANCE_SCALE,
    SDXL_DEFAULT_HEIGHT,
    SDXL_DEFAULT_NEGATIVE_PROMPT,
    SDXL_DEFAULT_STEPS,
    SDXL_DEFAULT_WIDTH,
)
from ml.worker.story_pipeline import (
    brief_key,
    build_story_brief,
    chapter_image_key,
    chapter_json_key,
    collect_previous_chapters,
    create_story_manifest,
    enqueue_job,
    get_json,
    manifest_key,
    plan_key,
    put_json,
    update_manifest_chapter,
)


def _render_story_image(job, *, s3_client, key: str) -> dict:
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


def handle_sdxl(job, *, s3_client, **_kwargs) -> dict:
    return _render_story_image(job, s3_client=s3_client, key=f"sdxl/{job.job_id}.png")


def handle_story_plan(job, *, s3_client, sqs_client, qwen_controller=None, **_kwargs) -> dict:
    unload_pipeline()
    if qwen_controller is not None:
        qwen_controller.ensure_started(wait_until_ready=True)

    brief = build_story_brief(job.payload)
    plan = build_story_plan(brief)
    manifest = create_story_manifest(story_id=job.story_id, brief=brief, plan=plan)

    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=brief_key(job.story_id), body=brief)
    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=plan_key(job.story_id), body=plan)
    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id), body=manifest)

    if manifest["chapters_total"] > 0:
        enqueue_job(
            sqs_client=sqs_client,
            story_id=job.story_id,
            job_type="chapter_generate",
            job_id=f"{job.story_id}:chapter:01",
            payload={"chapter_number": 1},
        )

    return {
        "status": "in_progress",
        "output_s3_key": manifest_key(job.story_id),
        "current_stage": "chapter_generate",
        "chapters_total": manifest["chapters_total"],
        "chapters_completed": 0,
        "chapters_text_completed": 0,
        "chapters_images_completed": 0,
        "story_title": manifest["title"],
    }


def handle_chapter_generate(job, *, s3_client, sqs_client, **_kwargs) -> dict:
    chapter_number = int(job.payload["chapter_number"])
    current_manifest = get_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id))
    plan = get_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=plan_key(job.story_id))
    brief = current_manifest["brief"]
    chapter_outline = next(
        chapter
        for chapter in plan["chapters"]
        if int(chapter["chapter_number"]) == chapter_number
    )
    previous_chapters = collect_previous_chapters(current_manifest, chapter_number)
    chapter_content = build_chapter(
        brief=brief,
        plan=plan,
        chapter_outline=chapter_outline,
        previous_chapters=previous_chapters,
    )

    chapter_key = chapter_json_key(job.story_id, chapter_number)
    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=chapter_key, body=chapter_content)

    next_manifest = update_manifest_chapter(
        current_manifest,
        chapter_number,
        {
            "status": "text_completed",
            "chapter_s3_key": chapter_key,
            "visual_prompt": chapter_content["visual_prompt"],
            "content": chapter_content,
        },
    )

    next_chapter_number = chapter_number + 1
    has_next_chapter = any(
        int(chapter["chapter_number"]) == next_chapter_number for chapter in next_manifest["chapters"]
    )
    if has_next_chapter:
        enqueue_job(
            sqs_client=sqs_client,
            story_id=job.story_id,
            job_type="chapter_generate",
            job_id=f"{job.story_id}:chapter:{next_chapter_number:02d}",
            payload={"chapter_number": next_chapter_number},
        )
        next_manifest["status"] = "in_progress"
        next_manifest["phase"] = "text"
        current_stage = "chapter_generate"
    else:
        next_manifest["status"] = "text_completed"
        next_manifest["phase"] = "text_ready_for_images"
        current_stage = "text_completed"

    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id), body=next_manifest)

    return {
        "status": next_manifest["status"],
        "output_s3_key": manifest_key(job.story_id),
        "current_stage": current_stage,
        "chapters_total": next_manifest["chapters_total"],
        "chapters_completed": next_manifest["chapters_completed"],
        "chapters_text_completed": next_manifest["chapters_text_completed"],
        "chapters_images_completed": next_manifest["chapters_images_completed"],
        "current_chapter": chapter_number,
    }


def handle_story_render_images(job, *, s3_client, sqs_client, qwen_controller=None, **_kwargs) -> dict:
    current_manifest = get_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id))
    if current_manifest.get("chapters_text_completed", 0) != current_manifest.get("chapters_total", 0):
        raise ValueError("Story text is not fully generated yet")

    first_chapter = next(
        (chapter for chapter in current_manifest["chapters"] if chapter.get("status") == "text_completed"),
        None,
    )
    if first_chapter is None:
        raise ValueError("No chapter is ready for image generation")

    if qwen_controller is not None:
        qwen_controller.stop()

    current_manifest["phase"] = "images"
    current_manifest["status"] = "in_progress"
    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id), body=current_manifest)

    chapter_content = first_chapter["content"]
    chapter_number = int(first_chapter["chapter_number"])
    brief = current_manifest["brief"]
    enqueue_job(
        sqs_client=sqs_client,
        story_id=job.story_id,
        job_type="chapter_image",
        job_id=f"{job.story_id}:image:{chapter_number:02d}",
        payload={
            "chapter_number": chapter_number,
            "prompt": chapter_content["visual_prompt"],
            "negative_prompt": chapter_content.get("negative_prompt", SDXL_DEFAULT_NEGATIVE_PROMPT),
            "style": brief["art_direction"]["style"],
            "width": job.payload.get("width", SDXL_DEFAULT_WIDTH),
            "height": job.payload.get("height", SDXL_DEFAULT_HEIGHT),
            "num_inference_steps": job.payload.get("num_inference_steps", SDXL_DEFAULT_STEPS),
            "guidance_scale": job.payload.get("guidance_scale", SDXL_DEFAULT_GUIDANCE_SCALE),
        },
    )

    return {
        "status": "in_progress",
        "output_s3_key": manifest_key(job.story_id),
        "current_stage": "chapter_image",
        "chapters_total": current_manifest["chapters_total"],
        "chapters_completed": current_manifest["chapters_completed"],
        "chapters_text_completed": current_manifest["chapters_text_completed"],
        "chapters_images_completed": current_manifest["chapters_images_completed"],
        "story_title": current_manifest["title"],
    }


def handle_chapter_image(job, *, s3_client, sqs_client, qwen_controller=None, **_kwargs) -> dict:
    chapter_number = int(job.payload["chapter_number"])
    image_key = chapter_image_key(job.story_id, chapter_number)
    image_result = _render_story_image(job, s3_client=s3_client, key=image_key)
    current_manifest = get_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id))
    next_manifest = update_manifest_chapter(
        current_manifest,
        chapter_number,
        {
            "status": "completed",
            "image_s3_key": image_key,
            "image_params": {
                "width": image_result["width"],
                "height": image_result["height"],
                "num_inference_steps": image_result["num_inference_steps"],
                "guidance_scale": image_result["guidance_scale"],
            },
        },
    )

    next_chapter_number = chapter_number + 1
    next_image_chapter = next(
        (
            chapter
            for chapter in next_manifest["chapters"]
            if int(chapter["chapter_number"]) == next_chapter_number and chapter.get("status") == "text_completed"
        ),
        None,
    )
    if next_image_chapter is not None:
        brief = next_manifest["brief"]
        chapter_content = next_image_chapter["content"]
        enqueue_job(
            sqs_client=sqs_client,
            story_id=job.story_id,
            job_type="chapter_image",
            job_id=f"{job.story_id}:image:{next_chapter_number:02d}",
            payload={
                "chapter_number": next_chapter_number,
                "prompt": chapter_content["visual_prompt"],
                "negative_prompt": chapter_content.get("negative_prompt", SDXL_DEFAULT_NEGATIVE_PROMPT),
                "style": brief["art_direction"]["style"],
                "width": job.payload.get("width", SDXL_DEFAULT_WIDTH),
                "height": job.payload.get("height", SDXL_DEFAULT_HEIGHT),
                "num_inference_steps": job.payload.get("num_inference_steps", SDXL_DEFAULT_STEPS),
                "guidance_scale": job.payload.get("guidance_scale", SDXL_DEFAULT_GUIDANCE_SCALE),
            },
        )
        next_manifest["status"] = "in_progress"
        next_manifest["phase"] = "images"
        current_stage = "chapter_image"
    else:
        next_manifest["status"] = "completed"
        next_manifest["phase"] = "images_completed"
        current_stage = "completed"
        unload_pipeline()
        if qwen_controller is not None:
            qwen_controller.ensure_started(wait_until_ready=False)

    put_json(s3_client=s3_client, bucket=BUCKET_OUTPUTS, key=manifest_key(job.story_id), body=next_manifest)

    return {
        "status": next_manifest["status"],
        "output_s3_key": manifest_key(job.story_id),
        "current_stage": current_stage,
        "chapters_total": next_manifest["chapters_total"],
        "chapters_completed": next_manifest["chapters_completed"],
        "chapters_text_completed": next_manifest["chapters_text_completed"],
        "chapters_images_completed": next_manifest["chapters_images_completed"],
        "current_chapter": chapter_number,
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
