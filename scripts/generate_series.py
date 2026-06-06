#!/usr/bin/env python3
"""
generate_series.py — draft a 4-5 part Stories reading path.

This is intentionally review-first: it writes a draft JSON file under
data/series_drafts/ and does not publish articles or update data/stories/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_client import GeminiClient, parse_json_response

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = PROJECT_ROOT / "data" / "series_drafts"

DEFAULT_MODEL = "gemini-3.1-flash-lite"

SMALL_TITLE_WORDS = {
    "a", "an", "and", "as", "at", "but", "by", "for", "from",
    "in", "into", "nor", "of", "on", "or", "the", "to", "with",
}


SERIES_OUTLINE_PROMPT = """
You are an editor for a daily English news reading practice site for Traditional-Chinese-speaking learners in Taiwan.

Create a 5-part long-form reading path for this topic:
{topic}

Audience and product context:
- Readers are intermediate English learners, around CEFR B1-B2.
- The site is English-first. Chinese is for support, not the main reading experience.
- The topic should help readers understand a real long-running news story, not just today's headline.
- Prefer public-interest stories with background, causes, stakeholders, turning points, and future questions.
- Keep wording neutral and factual.
- Avoid sensational framing.
- Do not fabricate specific fresh facts, dates, numbers, or quotes.

STYLE TARGET — source-led reading comprehension, not a short news summary:

Each article in the series should read like a serious reading-comprehension packet,
modeled on real journalism used in graduate-level English reading exams.
This means:

1. BYLINE HEADER: Every article must open with a clear citation line, for example:
   "How AI Is Draining America's Power Grid," by Jane Smith, The Atlantic, March 2024

2. ATTRIBUTION IN EVERY PARAGRAPH: Each paragraph should weave in the source.
   Do not write free-floating claims. Use patterns like:
   - "According to [outlet]..."
   - "[Expert name], a [title] at [institution], said..."
   - "[Outlet] reports that..."
   - "In a [date] report, [agency] found that..."

3. DIRECT QUOTE DESIGN: Plan at least one real-sounding quote per source
   (attributed to a named official, researcher, or executive — never fabricated).
   Quote slots should be specific: not "an expert said" but
   "[Energy Secretary / IEA chief economist / company spokesperson] said..."

4. MULTI-SOURCE STRUCTURE: Each article should draw from 2-3 distinct source types:
   - A news report (establishes facts and current events)
   - An analysis or explainer (adds context and interpretation)
   - An expert Q&A or official report (adds authority and depth)

5. FACTUAL ANCHORING: At least 2-3 specific, attributable facts per article
   (numbers, dates, policy names, legal terms) — each tied to a named source.

Design the series as a learning path:
1. Background: how the issue began and why it matters
2. Key players: people, institutions, countries, companies, or communities involved
3. Turning point: the major recent change or conflict
4. Consequences: effects on ordinary people, policy, markets, health, society, or Taiwan
5. What comes next: unresolved questions and possible future paths

Output valid JSON only. No markdown fences, no preamble:
{
  "id": "short-kebab-case-id",
  "title": "Clear English series title",
  "titleZh": "繁體中文標題",
  "subtitle": "One sentence subtitle",
  "subtitleZh": "繁體中文副標",
  "description": "Two to three sentences explaining why this series matters.",
  "descriptionZh": "繁體中文：兩到三句說明這個專題為什麼重要。",
  "category": "politics|economics|technology|energy|society|health|public-health",
  "status": "draft",
  "editorNotesZh": "繁體中文：說明為什麼這個主題適合做連載，以及讀者會學到什麼。",
  "parts": [
    {
      "part": 1,
      "title": "Article title",
      "titleZh": "繁體中文文章標題",
      "bylinePlan": "Suggested byline format, e.g. 'by [reporter type], [outlet type], [approximate date range]'",
      "angle": "The specific angle this article should explain.",
      "angleZh": "繁體中文：這篇要說明的角度。",
      "learningGoal": "What the learner should understand after reading.",
      "learningGoalZh": "繁體中文：讀完這篇後應該理解什麼。",
      "keyQuestions": ["Question 1", "Question 2", "Question 3"],
      "keyQuestionsZh": ["繁體中文問題 1", "繁體中文問題 2", "繁體中文問題 3"],
      "sourcePlan": [
        {
          "sourceType": "news report|analysis|official report|research|explainer|expert Q&A",
          "searchHint": "source search phrase",
          "whyUseful": "What this source should contribute to the article.",
          "whyUsefulZh": "繁體中文：這個來源可以補強什麼。",
          "attributionExample": "Example of how this source would be cited inline, e.g. 'According to a 2024 IEA report...' or 'WIRED reports that...'"
        }
      ]
    }
  ]
}
""".strip()


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    base = re.sub(r"-+", "-", base)
    return base[:70].strip("-") or "story-draft"


def title_case(text: str) -> str:
    words = re.split(r"(\s+)", text.strip())
    titled: list[str] = []
    word_index = 0
    word_count = len([w for w in words if w.strip()])
    for token in words:
        if not token.strip():
            titled.append(token)
            continue
        lower = token.lower()
        if 0 < word_index < word_count - 1 and lower in SMALL_TITLE_WORDS:
            titled.append(lower)
        elif lower == "ai":
            titled.append("AI")
        else:
            titled.append(lower[:1].upper() + lower[1:])
        word_index += 1
    return "".join(titled)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def fallback_outline(topic: str) -> dict[str, Any]:
    """No-API fallback so the user can inspect the draft shape immediately."""
    story_id = slugify(topic)
    title = title_case(topic)
    return {
        "id": story_id,
        "title": title,
        "titleZh": f"{title}：五篇追蹤專題",
        "subtitle": "A five-part reading path for understanding a long-running news story.",
        "subtitleZh": "用五篇文章理解一條長期發展的新聞故事。",
        "description": (
            "This draft was created without calling an AI model. Use it to review the "
            "series format before generating a full AI-planned outline."
        ),
        "descriptionZh": (
            "這份草稿沒有呼叫 AI 模型，主要用來確認連載格式。換成本機新的 Gemini key 後，"
            "可以產生更貼近真實新聞脈絡的大綱。"
        ),
        "category": "society",
        "status": "draft",
        "editorNotesZh": (
            "這是沒有使用 API 的模板草稿。確認格式與頁面方向後，可以設定 GEMINI_API_KEY "
            "再產生更完整的大綱。"
        ),
        "parts": [
            {
                "part": 1,
                "title": f"{title}: Background",
                "titleZh": "背景：這件事從哪裡開始",
                "angle": "Explain how the issue began and why it matters.",
                "angleZh": "說明事件起點，以及它為什麼值得長期追蹤。",
                "learningGoal": "Understand the basic history and core vocabulary.",
                "learningGoalZh": "讀者能理解基本背景和核心英文詞彙。",
                "keyQuestions": [
                    "What started this issue?",
                    "Why does it matter now?",
                    "Which facts should readers know first?",
                ],
                "keyQuestionsZh": [
                    "這個議題最早是怎麼開始的？",
                    "為什麼它現在重要？",
                    "讀者最先需要知道哪些事實？",
                ],
                "sourcePlan": [
                    {
                        "sourceType": "explainer",
                        "searchHint": f"{topic} background",
                        "whyUseful": "Provides a plain-language overview and timeline.",
                        "whyUsefulZh": "提供清楚的背景和時間線。",
                    },
                    {
                        "sourceType": "news report",
                        "searchHint": f"{topic} timeline",
                        "whyUseful": "Gives concrete events for the opening article.",
                        "whyUsefulZh": "提供第一篇文章可引用的具體事件。",
                    },
                ],
            },
            {
                "part": 2,
                "title": f"{title}: Key Players",
                "titleZh": "關鍵角色：誰在影響這件事",
                "angle": "Introduce the main people, institutions, and communities involved.",
                "angleZh": "介紹主要人物、機構、公司、國家或社群，以及他們各自想要什麼。",
                "learningGoal": "Understand who wants what, and why their interests differ.",
                "learningGoalZh": "讀者能理解不同角色的利益與衝突。",
                "keyQuestions": [
                    "Who are the main actors?",
                    "What does each side want?",
                    "Where do their interests conflict?",
                ],
                "keyQuestionsZh": [
                    "主要角色是誰？",
                    "各方想得到什麼？",
                    "他們的利益在哪裡衝突？",
                ],
                "sourcePlan": [
                    {
                        "sourceType": "analysis",
                        "searchHint": f"{topic} key players",
                        "whyUseful": "Explains stakeholder incentives and conflicts.",
                        "whyUsefulZh": "說明不同角色的動機與衝突。",
                    },
                    {
                        "sourceType": "news report",
                        "searchHint": f"{topic} stakeholders",
                        "whyUseful": "Adds quotes or examples from affected groups.",
                        "whyUsefulZh": "補充受影響族群或相關角色的例子。",
                    },
                ],
            },
            {
                "part": 3,
                "title": f"{title}: Turning Point",
                "titleZh": "轉折點：最近發生了什麼改變",
                "angle": "Explain the recent event that changed the story.",
                "angleZh": "說明最近讓事件升級或轉向的關鍵變化。",
                "learningGoal": "Understand the latest development without losing the larger context.",
                "learningGoalZh": "讀者能理解最新進展，同時不失去整體脈絡。",
                "keyQuestions": [
                    "What changed recently?",
                    "Why was this change important?",
                    "How did people respond?",
                ],
                "keyQuestionsZh": [
                    "最近發生了什麼變化？",
                    "這個變化為什麼重要？",
                    "各方如何回應？",
                ],
                "sourcePlan": [
                    {
                        "sourceType": "news report",
                        "searchHint": f"{topic} latest development",
                        "whyUseful": "Provides the newest concrete development.",
                        "whyUsefulZh": "提供最新的具體進展。",
                    },
                    {
                        "sourceType": "analysis",
                        "searchHint": f"{topic} turning point",
                        "whyUseful": "Explains why the development changes the story.",
                        "whyUsefulZh": "解釋為什麼這個進展構成轉折。",
                    },
                ],
            },
            {
                "part": 4,
                "title": f"{title}: Consequences",
                "titleZh": "影響：誰會受到衝擊",
                "angle": "Explain the effects on ordinary people, policy, markets, or society.",
                "angleZh": "說明它對一般人、政策、市場或社會造成的影響。",
                "learningGoal": "Connect the story to real-world consequences.",
                "learningGoalZh": "讀者能把新聞脈絡連到真實世界的後果。",
                "keyQuestions": [
                    "Who is affected most?",
                    "What costs or risks are growing?",
                    "What choices do decision-makers face?",
                ],
                "keyQuestionsZh": [
                    "誰受到最大影響？",
                    "哪些成本或風險正在上升？",
                    "決策者面臨什麼選擇？",
                ],
                "sourcePlan": [
                    {
                        "sourceType": "news report",
                        "searchHint": f"{topic} impact",
                        "whyUseful": "Shows effects on people, communities, or markets.",
                        "whyUsefulZh": "呈現對人、社群或市場的影響。",
                    },
                    {
                        "sourceType": "official report",
                        "searchHint": f"{topic} consequences",
                        "whyUseful": "Adds numbers, policy details, or expert context.",
                        "whyUsefulZh": "補充數據、政策細節或專家脈絡。",
                    },
                ],
            },
            {
                "part": 5,
                "title": f"{title}: What Comes Next",
                "titleZh": "下一步：接下來要看什麼",
                "angle": "Explain possible future paths and unresolved questions.",
                "angleZh": "說明未解問題、未來可能走向，以及讀者之後該注意什麼。",
                "learningGoal": "Understand what to watch for next in future news.",
                "learningGoalZh": "讀者能知道未來看到相關新聞時要抓哪些重點。",
                "keyQuestions": [
                    "What remains uncertain?",
                    "What could happen next?",
                    "Which signals should readers watch?",
                ],
                "keyQuestionsZh": [
                    "還有哪些事情不確定？",
                    "接下來可能發生什麼？",
                    "讀者未來應該注意哪些訊號？",
                ],
                "sourcePlan": [
                    {
                        "sourceType": "analysis",
                        "searchHint": f"{topic} what next",
                        "whyUseful": "Explains future scenarios without pretending to predict the future.",
                        "whyUsefulZh": "說明未來情境，但不假裝能預測未來。",
                    },
                    {
                        "sourceType": "explainer",
                        "searchHint": f"{topic} future outlook",
                        "whyUseful": "Helps close the series with clear watch points.",
                        "whyUsefulZh": "幫助整理這條故事線接下來的觀察重點。",
                    },
                ],
            },
        ],
    }


def validate_outline(outline: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = ["id", "title", "description", "category", "parts"]
    for key in required:
        if not outline.get(key):
            errors.append(f"缺少欄位：{key}")

    valid_categories = {
        "politics", "economics", "technology", "energy",
        "society", "health", "public-health",
    }
    if outline.get("category") not in valid_categories:
        errors.append(f"category 不合法：{outline.get('category')}")

    parts = outline.get("parts")
    if not isinstance(parts, list) or len(parts) not in (4, 5):
        errors.append("parts 必須是 4 或 5 篇")
    elif parts:
        for idx, part in enumerate(parts, 1):
            for key in ("title", "angle", "learningGoal", "keyQuestions"):
                if not part.get(key):
                    errors.append(f"parts[{idx}] 缺少欄位：{key}")
            if not part.get("sourcePlan") and not part.get("searchHints"):
                errors.append(f"parts[{idx}] 缺少欄位：sourcePlan")

    return errors


def generate_with_gemini(topic: str, model: str) -> dict[str, Any]:
    client = GeminiClient(model=model)
    prompt = SERIES_OUTLINE_PROMPT.replace("{topic}", topic)
    response = client.complete(
        prompt=prompt,
        temperature=0.4,
        max_tokens=4500,
        response_format="json",
    )
    outline = parse_json_response(response.content)
    if not isinstance(outline, dict):
        raise ValueError("Gemini 回傳的 JSON 不是 object")
    outline["_generation"] = {
        "provider": response.provider,
        "model": response.model,
        "tokensUsed": response.tokens_used,
        "durationSec": round(response.duration_sec, 2),
    }
    return outline


def write_draft(outline: dict[str, Any], topic: str, overwrite: bool) -> Path:
    DRAFT_DIR.mkdir(parents=True, exist_ok=True)
    outline.setdefault("id", slugify(topic))
    outline["id"] = slugify(outline["id"])
    outline["draftedAt"] = now_iso()
    outline["topic"] = topic

    path = DRAFT_DIR / f"{outline['id']}.json"
    if path.exists() and not overwrite:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = DRAFT_DIR / f"{outline['id']}-{stamp}.json"

    path.write_text(
        json.dumps(outline, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def render_preview_markdown(outline: dict[str, Any]) -> str:
    lines = [
        f"# {outline.get('title', '')}",
        "",
        f"**中文：** {outline.get('titleZh', '')}",
        "",
        f"**Subtitle:** {outline.get('subtitle', '')}",
        "",
        f"**副標：** {outline.get('subtitleZh', '')}",
        "",
        "## Description / 說明",
        "",
        f"**EN:** {outline.get('description', '')}",
        "",
        f"**ZH:** {outline.get('descriptionZh', outline.get('editorNotesZh', ''))}",
        "",
        "## Reading Path / 閱讀路徑",
        "",
    ]

    for part in outline.get("parts", []):
        lines.extend([
            f"### Part {part.get('part')}: {part.get('title', '')}",
            "",
            f"**中文標題：** {part.get('titleZh', '')}",
            "",
        ])
        if part.get("bylinePlan"):
            lines.extend([f"**Byline plan:** {part['bylinePlan']}", ""])
        lines.extend([
            "| English | 繁體中文 |",
            "| --- | --- |",
            f"| {part.get('angle', '')} | {part.get('angleZh', '')} |",
            f"| {part.get('learningGoal', '')} | {part.get('learningGoalZh', '')} |",
            "",
            "**Key Questions / 核心問題**",
            "",
        ])
        questions = part.get("keyQuestions") or []
        questions_zh = part.get("keyQuestionsZh") or []
        for idx, question in enumerate(questions):
            zh = questions_zh[idx] if idx < len(questions_zh) else ""
            lines.append(f"- {question} / {zh}")
        lines.extend(["", "**Source Plan / 來源規劃**", ""])
        source_plan = part.get("sourcePlan") or []
        for source in source_plan:
            attribution = source.get("attributionExample", "")
            attr_note = f" → *{attribution}*" if attribution else ""
            lines.append(
                f"- `{source.get('sourceType', 'source')}` **{source.get('searchHint', '')}**: "
                f"{source.get('whyUseful', '')} / {source.get('whyUsefulZh', '')}{attr_note}"
            )
        if not source_plan:
            for hint in part.get("searchHints") or []:
                lines.append(f"- {hint}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def write_preview(outline: dict[str, Any], draft_path: Path) -> Path:
    preview_path = draft_path.with_suffix(".md")
    preview_path.write_text(render_preview_markdown(outline), encoding="utf-8")
    return preview_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Draft a 4-5 part Stories outline for review."
    )
    parser.add_argument("--topic", required=True, help="連載主題，例如：AI data centers and energy")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model，預設 {DEFAULT_MODEL}")
    parser.add_argument(
        "--no-api",
        action="store_true",
        help="不呼叫 Gemini，只產生模板草稿。",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="如果同 id 草稿已存在，直接覆蓋。",
    )
    args = parser.parse_args()

    use_api = bool(os.getenv("GEMINI_API_KEY")) and not args.no_api
    try:
        outline = generate_with_gemini(args.topic, args.model) if use_api else fallback_outline(args.topic)
    except Exception as exc:
        print(f"⚠️ Gemini 產生失敗，改用模板草稿：{exc}", file=sys.stderr)
        outline = fallback_outline(args.topic)
        outline["_generation"] = {"fallbackReason": str(exc)}

    errors = validate_outline(outline)
    if errors:
        print("❌ 草稿格式需要修正：", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    path = write_draft(outline, args.topic, args.overwrite)
    preview_path = write_preview(outline, path)
    rel = path.relative_to(PROJECT_ROOT)
    preview_rel = preview_path.relative_to(PROJECT_ROOT)
    print(f"✓ 已產生連載草稿：{rel}")
    print(f"✓ 已產生中英對照預覽：{preview_rel}")
    print(f"  Title: {outline['title']}")
    print(f"  Category: {outline['category']}")
    print(f"  Parts: {len(outline['parts'])}")
    if "_generation" in outline:
        print(f"  Generation: {outline['_generation']}")
    print()
    print("下一步：打開這個 JSON 審閱大綱；確認 OK 後，再把它轉成正式 Stories 或產生文章。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
