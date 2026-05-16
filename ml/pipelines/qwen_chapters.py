from __future__ import annotations

import json
import os
import re
import textwrap
import urllib.error
import urllib.request
from typing import Any


QWEN_API_BASE_URL = os.environ.get("QWEN_API_BASE_URL", "").rstrip("/")
QWEN_MODEL = os.environ.get("QWEN_MODEL", "Qwen2.5-14B-Instruct")
QWEN_API_KEY = os.environ.get("QWEN_API_KEY", "local-dev")
QWEN_TIMEOUT_SECONDS = int(os.environ.get("QWEN_TIMEOUT_SECONDS", "300"))
QWEN_ALLOW_STUB_FALLBACK = os.environ.get("QWEN_ALLOW_STUB_FALLBACK", "1") == "1"
EC2_HOST_PRIVATE_IP_PLACEHOLDER = "__EC2_HOST_PRIVATE_IP__"


def _resolve_ec2_private_ip() -> str:
    request = urllib.request.Request(
        url="http://169.254.169.254/latest/meta-data/local-ipv4",
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return response.read().decode("utf-8").strip()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to resolve EC2 private IP: {exc.reason}") from exc


def _resolved_qwen_api_base_url() -> str:
    if not QWEN_API_BASE_URL:
        return ""
    if EC2_HOST_PRIVATE_IP_PLACEHOLDER not in QWEN_API_BASE_URL:
        return QWEN_API_BASE_URL
    return QWEN_API_BASE_URL.replace(EC2_HOST_PRIVATE_IP_PLACEHOLDER, _resolve_ec2_private_ip())


def _post_chat_completion(messages: list[dict[str, str]], temperature: float) -> dict[str, Any]:
    qwen_api_base_url = _resolved_qwen_api_base_url()
    if not qwen_api_base_url:
        raise RuntimeError("QWEN_API_BASE_URL is not configured")

    request = urllib.request.Request(
        url=f"{qwen_api_base_url}/chat/completions",
        data=json.dumps(
            {
                "model": QWEN_MODEL,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {QWEN_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=QWEN_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Qwen request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Qwen request failed: {exc.reason}") from exc


def _extract_json_content(response: dict[str, Any]) -> dict[str, Any]:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Qwen response did not include a valid message") from exc

    if isinstance(content, list):
        text_parts = [part.get("text", "") for part in content if isinstance(part, dict)]
        content = "".join(text_parts)

    if not isinstance(content, str):
        raise RuntimeError("Qwen response content must be a string")

    content = content.strip()

    fenced_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", content, flags=re.DOTALL)
    if fenced_match:
        content = fenced_match.group(1).strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        json_fragment = _extract_first_json_object(content)
        if json_fragment is None:
            raise RuntimeError("Qwen response did not contain valid JSON") from None
        return json.loads(json_fragment)


def _extract_first_json_object(content: str) -> str | None:
    start = content.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(content)):
        char = content[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
            continue
        if char == "}":
            depth -= 1
            if depth == 0:
                return content[start : index + 1]

    return None


def _chat_json(*, system_prompt: str, user_payload: dict[str, Any], temperature: float) -> dict[str, Any]:
    response = _post_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=temperature,
    )
    return _extract_json_content(response)


def _stub_story_plan(brief: dict[str, Any]) -> dict[str, Any]:
    child_name = brief["profile"]["child_name"]
    chapter_count = int(brief["constraints"]["chapter_count"])
    favorite_themes = ", ".join(brief["profile"]["favorite_themes"]) or "wonder"
    chapters = []
    for chapter_number in range(1, chapter_count + 1):
        chapters.append(
            {
                "chapter_number": chapter_number,
                "title": f"Chapter {chapter_number}: {child_name}'s new clue",
                "summary": f"{child_name} follows a new lead tied to {favorite_themes}.",
                "goal": "Move the adventure forward while keeping the tone reassuring.",
                "visual_focus": "Warm storybook scene with a clear focal subject and gentle wonder.",
            }
        )

    return {
        "title": f"The adventures of {child_name}",
        "logline": f"{child_name} discovers a magical path shaped by {favorite_themes}.",
        "world_description": brief["book_prompt"],
        "visual_style_prompt": brief["art_direction"]["style"],
        "chapters": chapters,
        "generation_mode": "stub",
    }


def _stub_chapter(
    brief: dict[str, Any],
    plan: dict[str, Any],
    chapter_outline: dict[str, Any],
    previous_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    child_name = brief["profile"]["child_name"]
    traits = ", ".join(brief["profile"]["traits"]) or "curious"
    important_people = ", ".join(brief["profile"]["important_people"]) or "a trusted friend"
    previous_summary = previous_chapters[-1]["summary"] if previous_chapters else "the adventure begins"
    setting = ", ".join(brief["profile"]["setting_preferences"]) or "an enchanted landscape"
    moral_goal = brief["profile"]["moral_or_goal"] or "trust and kindness"

    chapter_text = textwrap.dedent(
        f"""
        {child_name} stepped into {setting} with a {traits} heart. The memory of {previous_summary}
        still guided every choice, and that made this new moment feel connected to the path ahead.

        During this chapter, {child_name} noticed details that echoed the promise of the story:
        {chapter_outline['summary']}. With help from {important_people}, the challenge stayed gentle,
        meaningful, and shaped around the value of {moral_goal}.

        By the end of the chapter, {child_name} understood one more piece of the world described in
        {plan['logline']}. The scene closed on a hopeful image that naturally leads to the next chapter.
        """
    ).strip()

    return {
        "chapter_number": chapter_outline["chapter_number"],
        "title": chapter_outline["title"],
        "summary": chapter_outline["summary"],
        "chapter_text": chapter_text,
        "visual_prompt": (
            f"{child_name} in {setting}, {chapter_outline['visual_focus']}, "
            f"{brief['art_direction']['style']}, cohesive children's book illustration"
        ),
        "negative_prompt": brief["art_direction"]["negative_prompt"],
        "continuity_state": {
            "location": setting,
            "mood": brief["constraints"]["tone"],
            "important_people": brief["profile"]["important_people"],
        },
        "image_alt": f"{child_name} in a key scene from chapter {chapter_outline['chapter_number']}.",
        "generation_mode": "stub",
    }


def _call_or_stub(
    *,
    system_prompt: str,
    user_payload: dict[str, Any],
    temperature: float,
    stub_factory,
) -> dict[str, Any]:
    try:
        return _chat_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            temperature=temperature,
        )
    except RuntimeError:
        if not QWEN_ALLOW_STUB_FALLBACK:
            raise
        return stub_factory()


def build_story_plan(brief: dict[str, Any]) -> dict[str, Any]:
    system_prompt = textwrap.dedent(
        """
        You are a children's book planner.
        Return only valid JSON.
        Build a coherent book plan from the provided brief.
        Keep the tone age-appropriate and preserve personalization details.
        Keep chapter summaries concise and concrete.
        Output keys:
        - title
        - logline
        - world_description
        - visual_style_prompt
        - chapters: array of objects with chapter_number, title, summary, goal, visual_focus
        """
    ).strip()

    return _call_or_stub(
        system_prompt=system_prompt,
        user_payload={"brief": brief},
        temperature=0.6,
        stub_factory=lambda: _stub_story_plan(brief),
    )


def build_chapter(
    *,
    brief: dict[str, Any],
    plan: dict[str, Any],
    chapter_outline: dict[str, Any],
    previous_chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    system_prompt = textwrap.dedent(
        """
        You are writing one chapter of a children's book and one image prompt for that chapter.
        Return only valid JSON.
        The text must respect the brief, maintain continuity, and stay aligned with the chapter outline.
        Write in French when the brief language is "fr".
        Keep the chapter compact: target about 180 to 260 words, and do not exceed 320 words.
        The visual_prompt must be short, visual, image-ready, and written in English for SDXL.
        The visual_prompt must clearly mention:
        - main subject
        - location
        - mood
        - lighting
        - children's storybook style
        Output keys:
        - chapter_number
        - title
        - summary
        - chapter_text
        - visual_prompt
        - negative_prompt
        - continuity_state
        - image_alt
        """
    ).strip()

    return _call_or_stub(
        system_prompt=system_prompt,
        user_payload={
            "brief": brief,
            "plan": plan,
            "chapter_outline": chapter_outline,
            "previous_chapters": previous_chapters,
        },
        temperature=0.7,
        stub_factory=lambda: _stub_chapter(brief, plan, chapter_outline, previous_chapters),
    )
