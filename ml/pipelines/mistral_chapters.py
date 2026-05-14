from __future__ import annotations

import json
import os
import textwrap
import urllib.error
import urllib.request
from typing import Any


MISTRAL_API_BASE_URL = os.environ.get("MISTRAL_API_BASE_URL", "https://api.mistral.ai").rstrip("/")
MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.environ.get("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_TIMEOUT_SECONDS = int(os.environ.get("MISTRAL_TIMEOUT_SECONDS", "120"))
MISTRAL_ALLOW_STUB_FALLBACK = os.environ.get("MISTRAL_ALLOW_STUB_FALLBACK", "1") == "1"


def _post_chat_completion(messages: list[dict[str, str]], temperature: float, max_tokens: int) -> dict[str, Any]:
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY is not configured")

    request = urllib.request.Request(
        url=f"{MISTRAL_API_BASE_URL}/v1/chat/completions",
        data=json.dumps(
            {
                "model": MISTRAL_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=MISTRAL_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Mistral request failed ({exc.code}): {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Mistral request failed: {exc.reason}") from exc


def _extract_text_content(response: dict[str, Any]) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Mistral response did not include a valid message") from exc

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                chunks.append(item.get("text", ""))
        return "".join(chunks)

    raise RuntimeError("Mistral response content format is unsupported")


def _extract_json_content(response: dict[str, Any]) -> dict[str, Any]:
    content = _extract_text_content(response)

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise RuntimeError("Mistral response did not contain valid JSON") from None
        return json.loads(content[start : end + 1])


def _chat_json(*, system_prompt: str, user_payload: dict[str, Any], temperature: float, max_tokens: int) -> dict[str, Any]:
    response = _post_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
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
    max_tokens: int,
    stub_factory,
) -> dict[str, Any]:
    try:
        return _chat_json(
            system_prompt=system_prompt,
            user_payload=user_payload,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except RuntimeError:
        if not MISTRAL_ALLOW_STUB_FALLBACK:
            raise
        return stub_factory()


def build_story_plan(brief: dict[str, Any]) -> dict[str, Any]:
    system_prompt = textwrap.dedent(
        """
        You are a children's book planner.
        Return only valid JSON.
        Build a coherent book plan from the provided brief.
        Keep the tone age-appropriate and preserve personalization details.
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
        max_tokens=2200,
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
        max_tokens=3500,
        stub_factory=lambda: _stub_chapter(brief, plan, chapter_outline, previous_chapters),
    )
