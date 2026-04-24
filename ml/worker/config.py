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
