#!/usr/bin/env python3
"""
weekly_series_pipeline.py — fully automated weekly Stories pipeline.

Runs every Monday via GitHub Actions (weekly_series.yml).
Steps:
  1. Ask Gemini to pick a topic not yet covered
  2. Generate a 5-part series outline
  3. Generate all 5 articles
  4. Publish to data/published/<date>/articles/
  5. Create data/stories/<id>.json

Usage (local test):
    uv run python scripts/weekly_series_pipeline.py
    uv run python scripts/weekly_series_pipeline.py --topic "custom topic"
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from llm_client import GeminiClient, parse_json_response
from generate_series import (
    generate_with_gemini as generate_outline,
    validate_outline,
    slugify,
)
from generate_series_article import (
    assemble_article_json,
    build_article_prompt,
    generate_part,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_DIR = PROJECT_ROOT / "data" / "published"
STORIES_DIR = PROJECT_ROOT / "data" / "stories"
DRAFT_DIR = PROJECT_ROOT / "data" / "series_drafts"

DEFAULT_MODEL = "gemini-3.1-flash-lite"

TOPIC_SELECTION_PROMPT = """
You are an editor for a daily English news reading practice site for CEFR B1-B2 learners in Taiwan.

Suggest ONE topic for a 5-part long-form reading series. The topic must:
- Be a real, ongoing international news story with historical context
- Have clear background, key players, turning points, consequences, and future questions
- Be relevant to global citizens, not just one country
- Be neutral and educational, not sensational
- Be different from these already-covered topics: {existing_topics}

Return ONLY a short English topic phrase (5-10 words), no explanation, no punctuation at the end.
Examples of good topics:
- Global semiconductor supply chain tensions
- The rise of antimicrobial resistance
- Arctic geopolitics and resource competition
- Central bank digital currencies
""".strip()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_existing_series_ids() -> list[str]:
    if not STORIES_DIR.exists():
        return []
    ids = []
    for f in STORIES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            ids.append(data.get("title", f.stem))
        except Exception:
            ids.append(f.stem)
    return ids


def pick_topic(model: str, existing: list[str]) -> str:
    client = GeminiClient(model=model)
    existing_str = ", ".join(existing) if existing else "none yet"
    prompt = TOPIC_SELECTION_PROMPT.replace("{existing_topics}", existing_str)
    response = client.complete(prompt=prompt, temperature=0.7, max_tokens=50)
    topic = response.content.strip().strip('"').strip("'").strip(".")
    print(f"  → Gemini 選題：{topic}")
    return topic


def publish_articles(
    outline: dict,
    parts: list[dict],
    date_str: str,
) -> list[str]:
    """Write article JSONs to data/published/<date>/articles/ and return slugs."""
    articles_dir = PUBLISHED_DIR / date_str / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    slugs = []
    for part_data, part_meta in zip(parts, outline["parts"]):
        slug = part_data["slug"]
        dest = articles_dir / f"{slug}.json"
        dest.write_text(
            json.dumps(part_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        slugs.append(slug)
        print(f"  ✓ 發布：{slug}")
    return slugs


def create_story_config(outline: dict, slugs: list[str]) -> Path:
    STORIES_DIR.mkdir(parents=True, exist_ok=True)
    series_id = outline["id"]

    parts = outline.get("parts", [])
    articles = []
    for i, slug in enumerate(slugs):
        part_meta = parts[i] if i < len(parts) else {}
        articles.append({
            "slug": slug,
            "label": f"Part {i + 1}",
            "note": part_meta.get("angle", ""),
        })

    config = {
        "id": series_id,
        "title": outline.get("title", ""),
        "subtitle": outline.get("subtitle", ""),
        "description": outline.get("description", ""),
        "category": outline.get("category", "society"),
        "status": "active",
        "updatedAt": now_iso(),
        "cadence": "5-part reading path. Complete series available.",
        "articles": articles,
    }

    path = STORIES_DIR / f"{series_id}.json"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"  ✓ Stories 書籤：data/stories/{series_id}.json")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Weekly automated Stories pipeline")
    parser.add_argument("--topic", help="覆蓋自動選題，指定主題")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--date", help="發布日期 YYYY-MM-DD，預設今天 UTC")
    args = parser.parse_args()

    date_str = args.date or today_utc()
    print(f"\n📅 發布日期：{date_str}")

    # Step 1: pick topic
    print("\n【Step 1】選題")
    existing = load_existing_series_ids()
    topic = args.topic or pick_topic(args.model, existing)
    series_id = slugify(topic)

    # Skip if already exists
    if (STORIES_DIR / f"{series_id}.json").exists():
        print(f"⚠️  {series_id} 已存在，跳過本週。")
        return 0

    # Step 2: generate outline
    print(f"\n【Step 2】產生大綱：{topic}")
    try:
        outline = generate_outline(topic, args.model)
    except Exception as e:
        print(f"❌ 大綱產生失敗：{e}", file=sys.stderr)
        return 1

    errors = validate_outline(outline)
    if errors:
        print("❌ 大綱格式錯誤：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    outline["id"] = slugify(outline.get("id") or topic)
    print(f"  → 標題：{outline.get('title')}")
    print(f"  → 分類：{outline.get('category')}")

    # Step 3: generate articles
    print("\n【Step 3】產生文章")
    out_dir = DRAFT_DIR / outline["id"]
    out_dir.mkdir(parents=True, exist_ok=True)

    article_jsons = []
    for part_meta in outline["parts"]:
        try:
            path = generate_part(
                outline=outline,
                part=part_meta,
                model=args.model,
                overwrite=True,
                out_dir=out_dir,
            )
            article_data = json.loads(path.read_text(encoding="utf-8"))
            article_jsons.append(article_data)
        except Exception as e:
            print(f"❌ Part {part_meta.get('part')} 失敗：{e}", file=sys.stderr)
            return 1

    # Step 4: publish
    print("\n【Step 4】發布文章")
    slugs = publish_articles(outline, article_jsons, date_str)

    # Step 5: create story config
    print("\n【Step 5】建立 Stories 書籤")
    create_story_config(outline, slugs)

    print(f"\n✅ 完成：{outline.get('title')}")
    print(f"   系列 ID：{outline['id']}")
    print(f"   文章數：{len(slugs)}")
    print(f"   網址：/stories/{outline['id']}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
