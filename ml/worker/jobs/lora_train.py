import json
from typing import Any, Dict


def handle_lora_train(job: Dict[str, Any], *, s3_client, ddb_table, callbacks_queue_url: str, sqs_client):
    """
    Stub LoRA : à terme, entraînera un adapter LoRA à partir du dataset (Zero123)
    et sauvegardera les poids dans S3.

    Pour l'instant :
    - On log
    - On envoie un callback "lora_done"
    - On met à jour DynamoDB
    """
    story_id = job.get("story_id")
    payload = job.get("payload", {})

    print(f"[lora_train] Start job for story={story_id} payload={payload}")

    # TODO plus tard :
    # - lister les images dans dataset_bucket/dataset_prefix
    # - lancer un script de training LoRA (accelerate / peft / diffusers)
    # - sauvegarder le fichier .safetensors dans lora_bucket/lora_key

    callback_event = {
        "event_type": "lora_done",
        "story_id": story_id,
        "details": {
            "lora_bucket": payload.get("lora_bucket"),
            "lora_key": payload.get("lora_key"),
        },
    }

    print(f"[lora_train] Sending callback event: {callback_event}")

    sqs_client.send_message(
        QueueUrl=callbacks_queue_url,
        MessageBody=json.dumps(callback_event),
    )

    try:
        ddb_table.update_item(
            Key={"story_id": story_id},
            UpdateExpression="SET lora_status = :s",
            ExpressionAttributeValues={":s": "done"},
        )
    except Exception as e:
        print(f"[lora_train] DynamoDB update failed: {e}")
