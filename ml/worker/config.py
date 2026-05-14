import os


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
HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "stabilityai/stable-diffusion-xl-base-1.0")
HF_TOKEN = os.environ.get("HF_TOKEN")
STORYBOOK_OUTPUT_PREFIX = os.environ.get("STORYBOOK_OUTPUT_PREFIX", "stories")
QWEN_CONTROL_INSTANCE_NAME = os.environ.get("QWEN_CONTROL_INSTANCE_NAME", "bookgen-ecs-gpu")
QWEN_CONTROL_SERVICE_NAME = os.environ.get("QWEN_CONTROL_SERVICE_NAME", "bookgen-qwen")
QWEN_CONTROL_ENABLED = os.environ.get("QWEN_CONTROL_ENABLED", "1") != "0"

SDXL_DEFAULT_NEGATIVE_PROMPT = os.environ.get(
    "SDXL_DEFAULT_NEGATIVE_PROMPT",
    "blurry, low quality, deformed, disfigured, bad anatomy, extra limbs, duplicate",
)
SDXL_DEFAULT_WIDTH = int(os.environ.get("SDXL_DEFAULT_WIDTH", "512"))
SDXL_DEFAULT_HEIGHT = int(os.environ.get("SDXL_DEFAULT_HEIGHT", "512"))
SDXL_DEFAULT_STEPS = int(os.environ.get("SDXL_DEFAULT_STEPS", "20"))
SDXL_DEFAULT_GUIDANCE_SCALE = float(os.environ.get("SDXL_DEFAULT_GUIDANCE_SCALE", "6.5"))
