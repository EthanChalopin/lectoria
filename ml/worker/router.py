from ml.worker.handlers import (
    handle_chapter_generate,
    handle_chapter_image,
    handle_lora_train,
    handle_sdxl,
    handle_story_render_images,
    handle_story_plan,
    handle_zero123,
)


JOB_HANDLERS = {
    "chapter_generate": handle_chapter_generate,
    "chapter_image": handle_chapter_image,
    "lora_train": handle_lora_train,
    "sdxl": handle_sdxl,
    "story_render_images": handle_story_render_images,
    "story_plan": handle_story_plan,
    "zero123": handle_zero123,
}


def get_job_handler(job_type: str):
    try:
        return JOB_HANDLERS[job_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported job_type: {job_type}") from exc
