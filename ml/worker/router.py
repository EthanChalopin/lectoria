from ml.worker.handlers import handle_lora_train, handle_sdxl, handle_zero123


JOB_HANDLERS = {
    "lora_train": handle_lora_train,
    "sdxl": handle_sdxl,
    "zero123": handle_zero123,
}


def get_job_handler(job_type: str):
    try:
        return JOB_HANDLERS[job_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported job_type: {job_type}") from exc
