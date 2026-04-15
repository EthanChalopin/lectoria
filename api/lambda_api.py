import json
import os
import uuid
import datetime

import boto3

# --- Clients AWS ---
sqs = boto3.client("sqs")
dynamodb = boto3.resource("dynamodb")

# --- Variables d'environnement (config Lambda) ---
INFERENCE_QUEUE_URL = os.environ["INFERENCE_QUEUE_URL"]
DDB_STORIES_TABLE = os.environ["DDB_STORIES_TABLE"]

table = dynamodb.Table(DDB_STORIES_TABLE)


def _response(status_code: int, body: dict):
    """Helper pour formater les réponses HTTP API Gateway."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event, context):
    """
    Handler principal pour Lambda.
    Attendu par la config: handler = "lambda_api.lambda_handler"
    """
    try:
        print("[LAMBDA] Event reçu :", json.dumps(event))

        # Body JSON venant d'API Gateway v2 (HTTP API)
        body = event.get("body")
        if body is None:
            return _response(400, {"error": "Missing request body"})

        if isinstance(body, str):
            body = json.loads(body)

        prompt = body.get("prompt")
        style = body.get("style", "default")

        if not prompt:
            return _response(400, {"error": "Missing 'prompt' in body"})

        # On utilise un seul ID pour story + job (simple)
        story_id = str(uuid.uuid4())
        job_id = story_id

        # Enregistrement initial dans DynamoDB
        item = {
            "story_id": story_id,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
            "status": "queued",
            "prompt": prompt,
            "style": style,
        }
        print("[LAMBDA] PutItem DynamoDB:", item)
        table.put_item(Item=item)

        # Envoi du message dans la file SQS d'inférence
        message_body = {
            "job_id": job_id,
            "story_id": story_id,
            "job_type": "sdxl",
            "payload": {
                "prompt": prompt,
                "style": style,
            },
        }
        print("[LAMBDA] Envoi SQS:", message_body)
        sqs.send_message(
            QueueUrl=INFERENCE_QUEUE_URL,
            MessageBody=json.dumps(message_body),
        )

        return _response(200, {"job_id": job_id, "status": "queued"})

    except Exception as e:
        print("[LAMBDA] ERREUR :", repr(e))
        return _response(500, {"error": str(e)})


# Petit test local possible
if __name__ == "__main__":
    # Pour test local uniquement :
    os.environ.setdefault("AWS_REGION", "eu-west-1")
    os.environ.setdefault(
        "INFERENCE_QUEUE_URL",
        "https://sqs.eu-west-1.amazonaws.com/433101552109/bookgen-inference-queue",
    )
    os.environ.setdefault("DDB_STORIES_TABLE", "BookgenStories")

    fake_event = {
        "body": json.dumps(
            {
                "prompt": "A cute dragon reading a book in a magical library",
                "style": "storybook",
            }
        )
    }
    print("Réponse locale :", lambda_handler(fake_event, None))
