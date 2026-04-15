import json
from typing import Any, Dict


def handle_sd_infer(job: Dict[str, Any], *, s3_client, ddb_table, callbacks_queue_url: str, sqs_client):
    """
    Stub SDXL : à terme, chargera le modèle + LoRA, générera une image par chapitre.

    Pour l'instant :
    - On lit chapters (JSON) dans S3
    - On simule la génération en écrivant un petit fichier texte par chapitre dans S3
    - On envoie un callback "images_done"
    """
    story_id = job.get("story_id")
    payload = job.get("payload", {})

    print(f"[sd_infer] Start job for story={story_id} payload={payload}")

    chapters_bucket = payload.get("chapters_bucket")
    chapters_key = payload.get("chapters_key")
    output_bucket = payload.get("output_bucket")
    output_prefix = payload.get("output_prefix", "").rstrip("/") + "/"

    # Télécharger le fichier chapters.json
    obj = s3_client.get_object(Bucket=chapters_bucket, Key=chapters_key)
    chapters_data = json.loads(obj["Body"].read().decode("utf-8"))

    chapters = chapters_data.get("chapters", [])
    print(f"[sd_infer] Found {len(chapters)} chapters")

    # Simulation : on crée un fichier texte par chapitre
    for idx, ch in enumerate(chapters):
        desc = ch.get("image_prompt", ch.get("summary", ""))
        fake_content = f"FAKE IMAGE PLACEHOLDER for chapter {idx+1}: {desc}\n"
        key = f"{output_prefix}chapter_{idx+1:02d}.txt"

        s3_client.put_object(
            Bucket=output_bucket,
            Key=key,
            Body=fake_content.encode("utf-8"),
        )
        print(f"[sd_infer] Wrote placeholder {key}")

    callback_event = {
        "event_type": "images_done",
        "story_id": story_id,
        "details": {
            "output_bucket": output_bucket,
            "output_prefix": output_prefix,
            "num_chapters": len(chapters),
        },
    }

    sqs_client.send_message(
        QueueUrl=callbacks_queue_url,
        MessageBody=json.dumps(callback_event),
    )

    try:
        ddb_table.update_item(
            Key={"story_id": story_id},
            UpdateExpression="SET images_status = :s",
            ExpressionAttributeValues={":s": "done"},
        )
    except Exception as e:
        print(f"[sd_infer] DynamoDB update failed: {e}")
