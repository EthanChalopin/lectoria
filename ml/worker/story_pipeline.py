from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from ml.worker.config import INFERENCE_QUEUE_URL


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        parts = value.replace("\r", "\n").replace(",", "\n").split("\n")
        return [part.strip() for part in parts if part.strip()]
    return [str(value).strip()]


def build_story_brief(payload: dict[str, Any]) -> dict[str, Any]:
    chapter_count = int(payload.get("chapter_count", 4))
    if chapter_count < 1:
        chapter_count = 1

    return {
        "book_prompt": str(payload.get("book_prompt", "")).strip(),
        "language": str(payload.get("language", "fr")).strip() or "fr",
        "profile": {
            "child_name": str(payload.get("child_name", "Noah")).strip() or "Noah",
            "child_age": int(payload.get("child_age", 7)),
            "traits": _normalize_list(payload.get("child_traits")),
            "favorite_themes": _normalize_list(payload.get("favorite_themes")),
            "fears_to_avoid": _normalize_list(payload.get("fears_to_avoid")),
            "important_people": _normalize_list(payload.get("important_people")),
            "setting_preferences": _normalize_list(payload.get("setting_preferences")),
            "moral_or_goal": str(payload.get("moral_or_goal", "")).strip(),
        },
        "constraints": {
            "tone": str(payload.get("tone", "warm and adventurous")).strip() or "warm and adventurous",
            "target_age": str(payload.get("target_age", "6-8")).strip() or "6-8",
            "chapter_count": chapter_count,
        },
        "art_direction": {
            "style": str(payload.get("image_style", "storybook")).strip() or "storybook",
            "negative_prompt": str(
                payload.get(
                    "negative_prompt",
                    "blurry, low quality, deformed, disfigured, bad anatomy, extra limbs, duplicate",
                )
            ).strip(),
        },
    }


def story_prefix(story_id: str) -> str:
    return f"stories/{story_id}"


def brief_key(story_id: str) -> str:
    return f"{story_prefix(story_id)}/brief.json"


def plan_key(story_id: str) -> str:
    return f"{story_prefix(story_id)}/plan.json"


def manifest_key(story_id: str) -> str:
    return f"{story_prefix(story_id)}/manifest.json"


def chapter_json_key(story_id: str, chapter_number: int) -> str:
    return f"{story_prefix(story_id)}/chapters/{chapter_number:02d}.json"


def chapter_image_key(story_id: str, chapter_number: int) -> str:
    return f"{story_prefix(story_id)}/chapters/{chapter_number:02d}.png"


def put_json(*, s3_client, bucket: str, key: str, body: dict[str, Any]) -> None:
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8"),
        ContentType="application/json",
    )


def get_json(*, s3_client, bucket: str, key: str) -> dict[str, Any]:
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read().decode("utf-8"))


def enqueue_job(*, sqs_client, story_id: str, job_type: str, payload: dict[str, Any], job_id: str) -> None:
    sqs_client.send_message(
        QueueUrl=INFERENCE_QUEUE_URL,
        MessageBody=json.dumps(
            {
                "job_id": job_id,
                "story_id": story_id,
                "job_type": job_type,
                "payload": payload,
            }
        ),
    )


def create_story_manifest(*, story_id: str, brief: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    chapters = []
    for outline in plan.get("chapters", []):
        chapter_number = int(outline["chapter_number"])
        chapters.append(
            {
                "chapter_number": chapter_number,
                "title": outline.get("title", f"Chapter {chapter_number}"),
                "summary": outline.get("summary", ""),
                "status": "queued",
                "chapter_s3_key": None,
                "image_s3_key": None,
                "visual_prompt": None,
            }
        )

    return {
        "story_id": story_id,
        "status": "in_progress",
        "phase": "text",
        "language": brief["language"],
        "title": plan.get("title", "Untitled story"),
        "logline": plan.get("logline", ""),
        "world_description": plan.get("world_description", brief["book_prompt"]),
        "visual_style_prompt": plan.get("visual_style_prompt", brief["art_direction"]["style"]),
        "brief": brief,
        "plan_s3_key": plan_key(story_id),
        "brief_s3_key": brief_key(story_id),
        "chapters_total": len(chapters),
        "chapters_completed": 0,
        "chapters_text_completed": 0,
        "chapters_images_completed": 0,
        "chapters": chapters,
    }


def update_manifest_chapter(
    manifest: dict[str, Any],
    chapter_number: int,
    patch: dict[str, Any],
) -> dict[str, Any]:
    next_manifest = deepcopy(manifest)
    for chapter in next_manifest["chapters"]:
        if int(chapter["chapter_number"]) == chapter_number:
            chapter.update(patch)
            break

    next_manifest["chapters_completed"] = sum(
        1 for chapter in next_manifest["chapters"] if chapter.get("status") == "completed"
    )
    next_manifest["chapters_text_completed"] = sum(
        1 for chapter in next_manifest["chapters"] if chapter.get("status") in {"text_completed", "completed"}
    )
    next_manifest["chapters_images_completed"] = next_manifest["chapters_completed"]
    if (
        next_manifest.get("phase") == "images"
        and next_manifest["chapters_completed"] == next_manifest["chapters_total"]
    ):
        next_manifest["status"] = "completed"
    return next_manifest


def collect_previous_chapters(manifest: dict[str, Any], chapter_number: int) -> list[dict[str, Any]]:
    previous = []
    for chapter in manifest.get("chapters", []):
        current_number = int(chapter["chapter_number"])
        if current_number >= chapter_number:
            break
        if chapter.get("content"):
            previous.append(chapter["content"])
    return previous
