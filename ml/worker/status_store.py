from datetime import datetime, timezone

from botocore.exceptions import ClientError


class StatusStore:
    def __init__(self, table):
        self.table = table

    def create_job_if_not_exists(self, story_id: str, job_type: str) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            self.table.put_item(
                Item={
                    "story_id": story_id,
                    "job_type": job_type,
                    "status": "queued",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
                ConditionExpression="attribute_not_exists(story_id)",
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code != "ConditionalCheckFailedException":
                raise

    def update_job_status(
        self,
        story_id: str,
        status: str,
        *,
        extra_attrs: dict | None = None,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        update_expr = ["SET #status = :status", "updated_at = :updated_at"]
        expr_attr_names = {"#status": "status"}
        expr_attr_values = {
            ":status": status,
            ":updated_at": now_iso,
        }

        if extra_attrs:
            for idx, (key, value) in enumerate(extra_attrs.items()):
                key_name = f"#key{idx}"
                value_name = f":value{idx}"
                update_expr.append(f"{key_name} = {value_name}")
                expr_attr_names[key_name] = key
                expr_attr_values[value_name] = value

        self.table.update_item(
            Key={"story_id": story_id},
            UpdateExpression=", ".join(update_expr),
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
