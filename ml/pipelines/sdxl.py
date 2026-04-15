def generate_fake(prompt: str, style: str, job_id: str) -> dict:
    return {
        "note": "FAKE IMAGE – à remplacer par la vraie génération SDXL",
        "prompt": prompt,
        "style": style,
        "job_id": job_id,
    }
