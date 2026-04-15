import json
from typing import Any, Dict


def handle_zero123(job: Dict[str, Any], *, s3_client, ddb_table, callbacks_queue_url: str, sqs_client):
    """
    Stub Zero123 : à terme, prendra un portrait dans S3, génèrera N vues
    et les sauvegardera dans un prefix S3.

    Pour l'instant, on se contente de :
    - Lire les infos de payload
    - Simuler le travail
    - Envoyer un message de callback "zero123_done" dans la callbacks queue
    """
    story_id = job.get("story_id")
    payload = job.get("payload", {})

    print(f"[zero123] Start job for story={story_id} payload={payload}")

    # TODO plus tard :
    # - télécharger l'image input depuis S3
    # - lancer le modèle Zero123XL pour générer num_views images
    # - uploader les vues dans dataset_bucket/output_prefix

    # Simulation : on envoie juste un callback
    callback_event = {
        "event_type": "zero123_done",
        "story_id": story_id,
        "details": {
            "dataset_bucket": payload.get("output_bucket"),
            "dataset_prefix": payload.get("output_prefix"),
            "num_views": payload.get("num_views", 8),
        },
    }

    print(f"[zero123] Sending callback event: {callback_event}")

    sqs_client.send_message(
        QueueUrl=callbacks_queue_url,
        MessageBody=json.dumps(callback_event),
    )

    # On pourrait aussi mettre à jour un champ de statut dans DynamoDB
    try:
        ddb_table.update_item(
            Key={"story_id": story_id},
            UpdateExpression="SET zero123_status = :s",
            ExpressionAttributeValues={":s": "done"},
        )
    except Exception as e:
        print(f"[zero123] DynamoDB update failed: {e}")
