import json


class CallbackPublisher:
    def __init__(self, sqs_client, queue_url: str):
        self.sqs_client = sqs_client
        self.queue_url = queue_url

    def publish(self, body: dict) -> None:
        self.sqs_client.send_message(
            QueueUrl=self.queue_url,
            MessageBody=json.dumps(body),
        )

    def publish_completed(
        self,
        *,
        job_id: str,
        story_id: str,
        job_type: str,
        output_s3_key: str,
    ) -> None:
        self.publish(
            {
                "job_id": job_id,
                "story_id": story_id,
                "status": "completed",
                "job_type": job_type,
                "output_s3_key": output_s3_key,
            }
        )

    def publish_failed(
        self,
        *,
        job_id: str,
        story_id: str,
        job_type: str,
        error: str,
    ) -> None:
        self.publish(
            {
                "job_id": job_id,
                "story_id": story_id,
                "status": "failed",
                "job_type": job_type,
                "error": error,
            }
        )
