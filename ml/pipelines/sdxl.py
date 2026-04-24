from __future__ import annotations

from io import BytesIO

from ml.worker.config import HF_MODEL_ID, HF_TOKEN


_PIPELINE = None


def _build_pipeline():
    # Imported lazily so unit tests don't require GPU dependencies locally.
    import torch
    from diffusers import StableDiffusionXLPipeline

    pipeline = StableDiffusionXLPipeline.from_pretrained(
        HF_MODEL_ID,
        torch_dtype=torch.float16,
        variant="fp16",
        use_safetensors=True,
        token=HF_TOKEN,
    )
    pipeline = pipeline.to("cuda")
    pipeline.set_progress_bar_config(disable=True)
    pipeline.enable_attention_slicing()
    pipeline.enable_vae_slicing()
    return pipeline


def get_pipeline():
    global _PIPELINE
    if _PIPELINE is None:
        _PIPELINE = _build_pipeline()
    return _PIPELINE


def generate_image(
    *,
    prompt: str,
    negative_prompt: str,
    width: int,
    height: int,
    num_inference_steps: int,
    guidance_scale: float,
    seed: int | None = None,
):
    import torch

    pipeline = get_pipeline()
    generator = None
    if seed is not None:
        generator = torch.Generator(device="cuda").manual_seed(seed)

    result = pipeline(
        prompt=prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        num_inference_steps=num_inference_steps,
        guidance_scale=guidance_scale,
        generator=generator,
    )
    return result.images[0]


def render_png_bytes(**kwargs) -> bytes:
    image = generate_image(**kwargs)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
