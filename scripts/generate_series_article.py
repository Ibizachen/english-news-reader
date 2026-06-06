#!/usr/bin/env python3
"""
generate_series_article.py — generate a full article for one or all parts
of an approved Stories series outline.

Reads:  data/series_drafts/<id>.json
Writes: data/series_drafts/<id>/part-<n>.json   (article, for review)
        data/series_drafts/<id>/part-<n>.md      (bilingual preview)

Usage:
    uv run python scripts/generate_series_article.py --series ai-data-centers-energy-series --part 1
    uv run python scripts/generate_series_article.py --series ai-data-centers-energy-series --all
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm_client import GeminiClient, parse_json_response

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DRAFT_DIR = PROJECT_ROOT / "data" / "series_drafts"
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Rough token cost per article call — used for quota warnings.
TOKENS_PER_ARTICLE_ESTIMATE = 4500


ARTICLE_PROMPT = """
You are a writer for a daily English news reading practice site for Traditional-Chinese-speaking learners in Taiwan.

Write a full article for Part {part_num} of the series "{series_title}".

SERIES CONTEXT:
{series_description}

THIS PART:
- Title: {part_title}
- Angle: {part_angle}
- Byline plan: {byline_plan}
- Learning goal: {learning_goal}
- Key questions to answer: {key_questions}

SOURCE PLAN (the sources this article should draw from):
{source_plan}

STYLE REQUIREMENTS — follow these exactly:

1. BYLINE HEADER: The article must begin with a clear citation in the first paragraph's lead sentence,
   naming the publication(s) or report(s) it draws from.

2. ATTRIBUTION IN EVERY PARAGRAPH: Every factual claim must have a visible source.
   Use patterns like:
   - "According to [outlet]..."
   - "[Expert name], a [title] at [institution], said..."
   - "[Outlet] reports that..."
   - "A [year] report by [agency] found that..."

3. NO FABRICATED QUOTES OR STATISTICS: Do not invent direct quotes from real people
   or make up specific numbers. Use general attribution ("experts say", "reports suggest")
   when you cannot attribute a specific claim to a real, known source.

4. READING LEVEL: CEFR B1-B2. Sentences should be clear and not too complex,
   but the content should be substantive and informative.

5. LENGTH: 6-8 paragraphs, 600-900 words total in English.

6. TRANSLATION: Translate each paragraph into Traditional Chinese (繁體中文).
   Use Taiwan-style transliterations (川普 not 特朗普, 雪梨 not 悉尼, etc.).

OUTPUT — valid JSON only, no markdown fences, no preamble:
{
  "title": "Article title (clear, not clickbait)",
  "subtitle": "One sentence that extends the title with the most important detail.",
  "byline": "Adapted from reporting by [outlet type], [approximate date range]",
  "summary": {
    "en": "3-4 sentence plain summary for intermediate English learners.",
    "zh": "繁體中文：3-4 句摘要，用台灣用語。"
  },
  "paragraphs": [
    {
      "id": "p1",
      "en": "English paragraph text.",
      "zh": "繁體中文翻譯。"
    }
  ],
  "keyTerms": [
    {
      "term": "the exact word or phrase from the article",
      "partOfSpeech": "noun|verb|adjective|phrasal verb|idiom|abbreviation",
      "definitionEn": "Definition in English, in the sense used here.",
      "definitionZh": "中文解釋，描述此處的意思。",
      "noteZh": "Optional: why this word is tricky, e.g. it has a different common meaning."
    }
  ],
  "sources": [
    {
      "name": "outlet name, e.g. The Guardian",
      "url": "https://placeholder.example/search",
      "title": "Suggested article title to search for",
      "publishedAt": "2024-01-01T00:00:00Z"
    }
  ],
  "quiz": [
    {
      "id": "q1",
      "type": "detail|inference|vocabulary|main_idea",
      "question": "Question testing comprehension of a specific part of the article.",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct": "A|B|C|D",
      "explanationZh": "繁體中文：解釋為什麼這個答案正確，其他選項為何不對。"
    }
  ]
}

Rules for keyTerms: pick 4-6 words or phrases that B1-B2 learners are likely to find difficult.
Include the sentence from the article where the term appears in noteZh if useful.

Rules for quiz: write exactly 4 questions, one of each type: detail, inference, vocabulary, main_idea.
Questions should test the KEY QUESTIONS listed above, not trivial details.
""".strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def slugify(text: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return re.sub(r"-+", "-", base)[:70].strip("-") or "article"


def load_outline(series_id: str) -> dict[str, Any]:
    path = DRAFT_DIR / f"{series_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"找不到大綱：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def format_source_plan(source_plan: list[dict]) -> str:
    lines = []
    for s in source_plan:
        line = f"- [{s.get('sourceType', 'source')}] Search: \"{s.get('searchHint', '')}\""
        if s.get("whyUseful"):
            line += f"\n  Why useful: {s['whyUseful']}"
        if s.get("attributionExample"):
            line += f"\n  Attribution example: {s['attributionExample']}"
        lines.append(line)
    return "\n".join(lines) if lines else "(no source plan provided)"


def build_article_prompt(outline: dict[str, Any], part: dict[str, Any]) -> str:
    source_plan_text = format_source_plan(part.get("sourcePlan") or [])
    key_questions = "\n".join(
        f"  - {q}" for q in (part.get("keyQuestions") or [])
    )
    substitutions = {
        "part_num": str(part["part"]),
        "series_title": outline.get("title", ""),
        "series_description": outline.get("description", ""),
        "part_title": part.get("title", ""),
        "part_angle": part.get("angle", ""),
        "byline_plan": part.get("bylinePlan", "by a reporter at a major news outlet"),
        "learning_goal": part.get("learningGoal", ""),
        "key_questions": key_questions,
        "source_plan": source_plan_text,
    }
    prompt = ARTICLE_PROMPT
    for key, value in substitutions.items():
        prompt = prompt.replace("{" + key + "}", value)
    return prompt


def assemble_article_json(
    raw: dict[str, Any],
    outline: dict[str, Any],
    part: dict[str, Any],
    generation_meta: dict[str, Any],
) -> dict[str, Any]:
    series_id = outline.get("id", slugify(outline.get("title", "series")))
    total_parts = len(outline.get("parts", []))
    slug = f"{series_id}-part-{part['part']}"

    paragraphs = raw.get("paragraphs") or []
    word_count = sum(
        len(p.get("en", "").split()) for p in paragraphs
    )

    return {
        "id": f"series-{series_id}-part-{part['part']}",
        "slug": slug,
        "publishedAt": now_iso(),
        "category": outline.get("category", "society"),
        "title": raw.get("title", part.get("title", "")),
        "subtitle": raw.get("subtitle", ""),
        "byline": raw.get("byline", ""),
        "summary": raw.get("summary", {"en": "", "zh": ""}),
        "paragraphs": paragraphs,
        "wordCount": word_count,
        "readingLevel": "B1-B2",
        "keyTerms": raw.get("keyTerms") or [],
        "sources": raw.get("sources") or [],
        "series": {
            "id": series_id,
            "part": part["part"],
            "totalParts": total_parts,
        },
        "quiz": raw.get("quiz") or [],
        "aiGenerated": True,
        "aiModel": f"gemini/{generation_meta.get('model', DEFAULT_MODEL)}",
        "aiDisclaimer": "本文由 AI 根據連載大綱生成，事實與引用請以原始來源為準。審閱後方可發佈。",
        "_generation": generation_meta,
        "_seriesPartMeta": {
            "angle": part.get("angle", ""),
            "learningGoal": part.get("learningGoal", ""),
            "keyQuestions": part.get("keyQuestions") or [],
            "sourcePlan": part.get("sourcePlan") or [],
        },
    }


def render_article_preview(article: dict[str, Any]) -> str:
    series = article.get("series", {})
    lines = [
        f"# {article.get('title', '')}",
        f"*{article.get('subtitle', '')}*",
        "",
        f"**Byline:** {article.get('byline', '')}",
        f"**Series:** {series.get('id', '')} — Part {series.get('part')} / {series.get('totalParts')}",
        f"**Category:** {article.get('category', '')}  |  **Words:** {article.get('wordCount', 0)}",
        "",
        "---",
        "",
        "## Summary / 摘要",
        "",
        f"**EN:** {article.get('summary', {}).get('en', '')}",
        "",
        f"**ZH:** {article.get('summary', {}).get('zh', '')}",
        "",
        "---",
        "",
        "## Article / 文章",
        "",
    ]

    for para in article.get("paragraphs", []):
        lines.extend([
            f"**[EN]** {para.get('en', '')}",
            "",
            f"**[ZH]** {para.get('zh', '')}",
            "",
            "---",
            "",
        ])

    lines.extend(["## Key Terms / 詞彙", ""])
    for term in article.get("keyTerms", []):
        pos = f" *({term.get('partOfSpeech', '')})*" if term.get("partOfSpeech") else ""
        lines.append(f"- **{term.get('term', '')}**{pos}: {term.get('definitionEn', '')} / {term.get('definitionZh', '')}")
        if term.get("noteZh"):
            lines.append(f"  - 注意：{term['noteZh']}")
    lines.extend(["", "## Quiz / 測驗", ""])
    for q in article.get("quiz", []):
        opts = q.get("options", {})
        lines.extend([
            f"**Q{q.get('id', '')} [{q.get('type', '')}]** {q.get('question', '')}",
            f"  A. {opts.get('A', '')}",
            f"  B. {opts.get('B', '')}",
            f"  C. {opts.get('C', '')}",
            f"  D. {opts.get('D', '')}",
            f"  ✓ {q.get('correct', '')} — {q.get('explanationZh', '')}",
            "",
        ])

    lines.extend(["## Sources / 來源規劃", ""])
    for src in article.get("sources", []):
        lines.append(f"- {src.get('name', '')}: \"{src.get('title', '')}\" ({src.get('publishedAt', '')[:10]})")

    return "\n".join(lines).rstrip() + "\n"


def generate_part(
    outline: dict[str, Any],
    part: dict[str, Any],
    model: str,
    overwrite: bool,
    out_dir: Path,
) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"part-{part['part']}.json"
    md_path = out_dir / f"part-{part['part']}.md"

    if json_path.exists() and not overwrite:
        print(f"  ⏭  Part {part['part']} 已存在，略過（使用 --overwrite 覆蓋）")
        return json_path

    print(f"  → 產生 Part {part['part']}: {part.get('title', '')} ...", flush=True)
    t0 = time.monotonic()

    client = GeminiClient(model=model)
    prompt = build_article_prompt(outline, part)
    response = client.complete(
        prompt=prompt,
        temperature=0.5,
        max_tokens=5000,
        response_format="json",
    )

    raw = parse_json_response(response.content)
    if not isinstance(raw, dict):
        raise ValueError(f"Part {part['part']}: Gemini 回傳的 JSON 不是 object")

    elapsed = time.monotonic() - t0
    gen_meta = {
        "provider": response.provider,
        "model": response.model,
        "tokensUsed": response.tokens_used,
        "durationSec": round(elapsed, 2),
    }

    article = assemble_article_json(raw, outline, part, gen_meta)
    json_path.write_text(json.dumps(article, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_article_preview(article), encoding="utf-8")

    print(f"     ✓ {article['wordCount']} words, {response.tokens_used} tokens, {elapsed:.1f}s")
    return json_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a full article for one or all parts of a series outline."
    )
    parser.add_argument("--series", required=True, help="Series ID（大綱 JSON 的 id 欄位）")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--part", type=int, help="只產生第 N 篇（測試用）")
    group.add_argument("--all", action="store_true", help="產生全部篇章")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Gemini model（預設 {DEFAULT_MODEL}）")
    parser.add_argument("--overwrite", action="store_true", help="已存在的草稿直接覆蓋")
    args = parser.parse_args()

    try:
        outline = load_outline(args.series)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1

    parts = outline.get("parts", [])
    if not parts:
        print("❌ 大綱裡沒有 parts", file=sys.stderr)
        return 1

    if args.part:
        selected = [p for p in parts if p.get("part") == args.part]
        if not selected:
            valid = [p.get("part") for p in parts]
            print(f"❌ 找不到 Part {args.part}，有效值：{valid}", file=sys.stderr)
            return 1
    else:
        selected = parts

    series_id = outline.get("id", slugify(outline.get("title", "series")))
    out_dir = DRAFT_DIR / series_id
    total = len(selected)
    est_tokens = total * TOKENS_PER_ARTICLE_ESTIMATE

    print(f"\n連載：{outline.get('title', series_id)}")
    print(f"預計產生：{total} 篇文章（每篇約 {TOKENS_PER_ARTICLE_ESTIMATE:,} tokens，共約 {est_tokens:,} tokens）")
    print(f"輸出目錄：data/series_drafts/{series_id}/\n")

    errors = []
    for part in selected:
        try:
            generate_part(outline, part, args.model, args.overwrite, out_dir)
        except Exception as exc:
            print(f"  ❌ Part {part.get('part')} 失敗：{exc}", file=sys.stderr)
            errors.append((part.get("part"), exc))
            if total > 1:
                print("     繼續下一篇...", file=sys.stderr)

    print(f"\n{'✓' if not errors else '⚠️'} 完成：{total - len(errors)}/{total} 篇")
    if errors:
        for part_num, exc in errors:
            print(f"  - Part {part_num} 失敗：{exc}", file=sys.stderr)
        return 1

    print(f"\n下一步：打開 data/series_drafts/{series_id}/ 審閱文章草稿。")
    print("確認內容正確後，把 JSON 複製到 data/stories/ 並更新前端。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
