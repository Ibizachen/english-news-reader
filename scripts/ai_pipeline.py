"""
ai_pipeline.py — Phase 3 AI orchestrator.

Reads data/raw/<date>/headlines.json and produces final articles at
data/published/<date>/articles/<slug>.json by running four stages:

  1. topic_selection    pick 4-5 topics from candidate headlines
  2. article_synthesis  for each topic, write a 600-1000 word English article
  3. translation        translate paragraph-by-paragraph into 繁體中文
  4. quiz_generation    create 4 multiple-choice questions

Each stage uses scripts/ai_config.yaml for provider/model selection.
Tier-1 robustness (PHASE3_ADDENDUM §5):
  - JSON parse failures retry up to json_retry_max times, then fallback once
  - Translation paragraph count must match English paragraph count
  - Per-article try/except so one failure doesn't kill the batch
  - Synthesis & quiz field validation

Usage:
    uv run python scripts/ai_pipeline.py                  # produce all selected
    uv run python scripts/ai_pipeline.py --max-articles 1 # produce only 1
    uv run python scripts/ai_pipeline.py --topic-only     # stop after selection
    uv run python scripts/ai_pipeline.py --date 2026-05-05
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# Make sibling modules importable when run as `python scripts/ai_pipeline.py`
sys.path.insert(0, str(Path(__file__).resolve().parent))

import llm_client
import prompts

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_PUBLISHED = PROJECT_ROOT / "data" / "published"

VALID_CATEGORIES = {
    "politics",
    "economics",
    "technology",
    "energy",
    "society",
    "health",
    "public-health",
    "tcm",
}

# =============================================================================
# Stage runner: JSON retry + validation retry + fallback
# =============================================================================


@dataclass
class StageOutcome:
    parsed: dict[str, Any]
    provider: str
    model: str
    duration_sec: float
    tokens_used: int
    fallback_triggered: bool
    fallback_reason: str | None
    retries: int
    error_history: list[dict[str, str]] = field(default_factory=list)


class StageFailure(Exception):
    """Raised when a stage exhausts all retries and fallback."""

    def __init__(self, stage_name: str, history: list[dict[str, str]]):
        self.stage_name = stage_name
        self.history = history
        super().__init__(
            f"{stage_name} 階段失敗（共試過 {len(history)} 次），最後錯誤："
            + (history[-1]["error"] if history else "?")
        )


def _attempt(
    client: llm_client.BaseLLMClient,
    prompt_text: str,
    sc: llm_client.StageConfig,
    validator: Callable[[dict], str | None] | None,
) -> tuple[dict | None, llm_client.LLMResponse, str | None]:
    """Single LLM call → parse JSON → validate. Returns (parsed_or_None, resp, error_or_None)."""
    resp = client.complete(
        prompt_text,
        temperature=sc.temperature,
        max_tokens=sc.max_tokens,
        response_format="json",
    )
    try:
        parsed = llm_client.parse_json_response(resp.content)
    except json.JSONDecodeError as e:
        excerpt = resp.content[:200].replace("\n", " ")
        return None, resp, f"JSON 解析失敗：{e}（回應開頭：{excerpt}...）"

    if validator is not None:
        err = validator(parsed)
        if err:
            return None, resp, f"欄位驗證失敗：{err}"

    return parsed, resp, None


def run_stage(
    stage_name: str,
    base_prompt: str,
    *,
    validator: Callable[[dict], str | None] | None = None,
    log: Callable[[str], None] = print,
) -> StageOutcome:
    """Execute one pipeline stage with retries and optional fallback."""
    sc = llm_client.stage_config(stage_name)
    primary = llm_client.make_client(sc.provider, sc.model)
    fallback_client = llm_client.get_fallback_client_for_stage(stage_name)
    max_retries = int(llm_client.global_setting("json_retry_max", 3))

    history: list[dict[str, str]] = []
    last_error: str | None = None
    last_resp: llm_client.LLMResponse | None = None

    # ----- Phase 1: primary client, up to max_retries attempts -----
    for attempt_idx in range(max_retries):
        prompt_text = base_prompt
        if attempt_idx > 0 and last_error:
            prompt_text = (
                f"[Retry] Your previous response had an error: {last_error}\n"
                "IMPORTANT: Output ONLY valid JSON. No markdown code fences, "
                "no preamble, no trailing text. Fix the issue and output again.\n\n"
                + base_prompt
            )

        log(f"  → {primary.name}/{primary.model}（嘗試 {attempt_idx + 1}/{max_retries}）...")
        try:
            parsed, resp, error = _attempt(primary, prompt_text, sc, validator)
        except Exception as e:
            err_short = f"例外：{type(e).__name__}: {str(e)[:200]}"
            log(f"     ✗ {err_short}")
            history.append({"client": f"{primary}", "attempt": str(attempt_idx + 1), "error": err_short})
            last_error = err_short
            continue

        last_resp = resp
        if error is None and parsed is not None:
            return StageOutcome(
                parsed=parsed,
                provider=primary.name,
                model=primary.model,
                duration_sec=resp.duration_sec,
                tokens_used=resp.tokens_used,
                fallback_triggered=False,
                fallback_reason=None,
                retries=attempt_idx,
                error_history=history,
            )

        log(f"     ✗ {error[:200]}")
        history.append({
            "client": f"{primary}",
            "attempt": str(attempt_idx + 1),
            "error": error or "?",
        })
        last_error = error

    # ----- Phase 2: fallback client, single attempt -----
    if fallback_client is not None:
        log(
            f"  ⚠️ 主 provider 試過 {max_retries} 次都失敗，"
            f"切換 fallback：{fallback_client.name}/{fallback_client.model}"
        )
        prompt_text = (
            f"[Note] A previous attempt with another model failed: {last_error}\n"
            "Output ONLY valid JSON. No markdown fences, no preamble.\n\n"
            + base_prompt
        )
        sc_fb = llm_client.StageConfig(
            provider=fallback_client.name,
            model=fallback_client.model,
            temperature=sc.temperature,
            max_tokens=sc.max_tokens,
        )
        try:
            parsed, resp, error = _attempt(fallback_client, prompt_text, sc_fb, validator)
        except Exception as e:
            err_short = f"例外：{type(e).__name__}: {str(e)[:200]}"
            log(f"     ✗ {err_short}")
            history.append({"client": f"{fallback_client}", "attempt": "fallback", "error": err_short})
            raise StageFailure(stage_name, history)

        if error is None and parsed is not None:
            return StageOutcome(
                parsed=parsed,
                provider=fallback_client.name,
                model=fallback_client.model,
                duration_sec=resp.duration_sec,
                tokens_used=resp.tokens_used,
                fallback_triggered=True,
                fallback_reason=last_error,
                retries=max_retries,
                error_history=history,
            )
        log(f"     ✗ {error[:200]}")
        history.append({
            "client": f"{fallback_client}",
            "attempt": "fallback",
            "error": error or "?",
        })

    raise StageFailure(stage_name, history)


# =============================================================================
# Validators (PHASE3_ADDENDUM §5.4, §5.2)
# =============================================================================


def _validate_topic_selection(parsed: dict) -> str | None:
    topics = parsed.get("selected_topics")
    if not isinstance(topics, list) or len(topics) < 1:
        return "selected_topics 必須為非空 list"
    if len(topics) > 8:
        return f"selected_topics 過多（{len(topics)}）"
    for i, t in enumerate(topics):
        for key in ("topic_title", "category", "source_urls"):
            if key not in t:
                return f"selected_topics[{i}] 缺欄位 {key}"
        if t["category"] not in VALID_CATEGORIES:
            return f"selected_topics[{i}].category={t['category']} 不在合法類別中"
        if not isinstance(t["source_urls"], list) or not t["source_urls"]:
            return f"selected_topics[{i}].source_urls 必須為非空 list"
    return None


# Outlet detection — used to flag hallucinated citations.
# Substring-match outlets (their names are unique enough to find via lowercase substring).
_SUBSTRING_OUTLETS = [
    "reuters", "bbc", "guardian", "npr", "al jazeera", "aljazeera",
    "deutsche welle", "politico", "the verge", "ars technica",
    "stat news", "china daily", "scmp", "south china morning post",
]
# Whole-word abbreviations (case-sensitive to avoid matching "ap" inside other words).
_WORD_OUTLETS = ["AP", "WHO", "DW"]


def _check_citations(body: str, source_names: list[str]) -> str | None:
    """Verify that every outlet mentioned in the article body is one we actually
    fed to the LLM. Catches hallucinated 'as reported by Reuters' when Reuters
    wasn't in the input.
    """
    body_lower = body.lower()
    sources_blob = " ".join(source_names).lower()

    for outlet in _SUBSTRING_OUTLETS:
        if outlet in body_lower and outlet not in sources_blob:
            return (
                f"文章引用了「{outlet}」但這個 outlet 不在原始來源 {source_names} 裡 "
                f"— 可能是幻覺出來的引用，請只引用 sources_used 列出的來源"
            )
    for outlet in _WORD_OUTLETS:
        if re.search(rf"\b{outlet}\b", body) and outlet.lower() not in sources_blob:
            return (
                f"文章引用了「{outlet}」但這個 outlet 不在原始來源 {source_names} 裡 "
                f"— 可能是幻覺出來的引用"
            )
    return None


def make_synthesis_validator(source_names: list[str]) -> Callable[[dict], str | None]:
    """Validator factory that checks structural fields AND citation honesty."""

    def _check(parsed: dict) -> str | None:
        for key in ("title", "summary_en", "body", "sources_used"):
            if key not in parsed:
                return f"缺欄位 {key}"
        body = parsed.get("body") or ""
        if not isinstance(body, str) or not body.strip():
            return "body 為空"
        word_count = len(body.split())
        if word_count < 500 or word_count > 1200:
            return f"字數 {word_count} 不在 500-1200 之間"
        paragraphs = [p for p in body.split("\n\n") if p.strip()]
        if len(paragraphs) < 4:
            return f"段落數 {len(paragraphs)} 少於 4"

        cite_err = _check_citations(body, source_names)
        if cite_err:
            return cite_err
        return None

    return _check


def _validate_key_terms(parsed: dict) -> str | None:
    """Validator for the standalone key_terms_extraction stage."""
    terms = parsed.get("key_terms")
    if not isinstance(terms, list):
        return "key_terms 必須為 list"
    if len(terms) < 2:
        return f"key_terms 太少（{len(terms)}），至少需要 2 個"
    if len(terms) > 6:
        return f"key_terms 過多（{len(terms)}），最多 6 個"
    for i, kt in enumerate(terms):
        for key in ("term", "definitionEn", "definitionZh"):
            if not kt.get(key):
                return f"key_terms[{i}] 缺欄位 {key}"
    return None


def make_key_terms_validator(article_body: str) -> Callable[[dict], str | None]:
    """Stricter validator: every term must literally appear in the article body
    (substring match, case-insensitive). Catches LLMs picking words from raw
    sources instead of the simplified article."""

    body_lower = article_body.lower()

    def _check(parsed: dict) -> str | None:
        base = _validate_key_terms(parsed)
        if base:
            return base
        for i, kt in enumerate(parsed["key_terms"]):
            term = (kt.get("term") or "").strip().lower()
            if not term:
                return f"key_terms[{i}].term 為空"
            # Allow loose match on first 4-5 chars to handle inflections
            # (e.g. "frame" in body via "framed", "drop out" in body via "dropped out").
            head = term.split()[0]
            stem = head[: max(4, len(head) - 2)]
            if stem and stem in body_lower:
                continue
            if term in body_lower:
                continue
            return (
                f"key_terms[{i}] 的「{kt['term']}」沒出現在文章中。"
                f"AI 可能是從原始來源材料挑了這個字，請改挑文章 body 真的有的字。"
            )
        return None

    return _check


def make_translation_validator(expected_paragraph_count: int) -> Callable[[dict], str | None]:
    """Closure that validates translation against the known English paragraph count."""

    def _check(parsed: dict) -> str | None:
        translated = parsed.get("translated_paragraphs")
        if not isinstance(translated, list):
            return "translated_paragraphs 必須為 list"
        if len(translated) != expected_paragraph_count:
            return (
                f"段落數不匹配：英文 {expected_paragraph_count} 段，"
                f"中文翻譯 {len(translated)} 段"
            )
        if not parsed.get("translated_summary"):
            return "缺 translated_summary"
        return None

    return _check


def _validate_quiz(parsed: dict) -> str | None:
    questions = parsed.get("questions")
    if not isinstance(questions, list) or len(questions) != 4:
        return f"questions 必須為 4 題（實際 {len(questions) if isinstance(questions, list) else '?'}）"
    expected_types = {"detail", "inference", "vocabulary", "main_idea"}
    seen_types: set[str] = set()
    for i, q in enumerate(questions):
        for key in ("type", "question", "options", "correct", "explanation_zh"):
            if key not in q:
                return f"questions[{i}] 缺欄位 {key}"
        if q["type"] not in expected_types:
            return f"questions[{i}].type={q['type']} 必須為 {expected_types}"
        seen_types.add(q["type"])
        opts = q.get("options") or {}
        if set(opts.keys()) != {"A", "B", "C", "D"}:
            return f"questions[{i}].options 必須有 A/B/C/D 四個鍵"
        if q["correct"] not in {"A", "B", "C", "D"}:
            return f"questions[{i}].correct={q['correct']} 必須為 A/B/C/D"
        if len((q.get("explanation_zh") or "").strip()) < 50:
            return f"questions[{i}].explanation_zh 太短（< 50 字元）"
    if seen_types != expected_types:
        return f"題型未涵蓋全部四類：{seen_types}"
    return None


# =============================================================================
# Helpers — slug, source matching, paragraph splitting
# =============================================================================


def slugify(title: str, when: datetime) -> str:
    base = title.lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    base = re.sub(r"-+", "-", base)
    if len(base) > 50:
        base = base[:50].rsplit("-", 1)[0]
    suffix = when.strftime("%b-%Y").lower()
    return f"{base}-{suffix}" if base else f"article-{suffix}"


def split_paragraphs(body: str) -> list[str]:
    return [p.strip() for p in body.split("\n\n") if p.strip()]


def gather_source_articles(urls: list[str], all_raw: list[dict]) -> list[dict]:
    by_url = {a["url"]: a for a in all_raw}
    return [by_url[u] for u in urls if u in by_url]


def load_raw_articles(date_str: str) -> list[dict]:
    headlines_file = DATA_RAW / date_str / "headlines.json"
    if not headlines_file.exists():
        raise FileNotFoundError(
            f"找不到 {headlines_file.relative_to(PROJECT_ROOT)}\n"
            "請先執行 Phase 2：uv run python scripts/fetch_news.py"
        )
    return json.loads(headlines_file.read_text(encoding="utf-8"))


# =============================================================================
# Stage runners (each calls run_stage with the right prompt + validator)
# =============================================================================


def stage_topic_selection(headlines: list[dict], log: Callable[[str], None]) -> StageOutcome:
    headlines_block = prompts.format_headlines_for_topic_selection(headlines)
    prompt_text = prompts.render(
        prompts.TOPIC_SELECTION_PROMPT, headlines_block=headlines_block
    )
    return run_stage(
        "topic_selection",
        prompt_text,
        validator=_validate_topic_selection,
        log=log,
    )


def stage_article_synthesis(
    topic: dict, source_articles: list[dict], log: Callable[[str], None]
) -> StageOutcome:
    src_block = prompts.format_source_articles_for_synthesis(source_articles)
    prompt_text = prompts.render(
        prompts.ARTICLE_SYNTHESIS_PROMPT,
        topic_title=topic["topic_title"],
        category=topic["category"],
        source_articles_block=src_block,
    )
    source_names = [sa["source"] for sa in source_articles]
    return run_stage(
        "article_synthesis",
        prompt_text,
        validator=make_synthesis_validator(source_names),
        log=log,
    )


def stage_key_terms_extraction(
    article_body: str, log: Callable[[str], None]
) -> StageOutcome:
    """Independent stage: extract tricky vocabulary from the synthesized body only."""
    prompt_text = prompts.render(
        prompts.KEY_TERMS_EXTRACTION_PROMPT, article_body=article_body
    )
    return run_stage(
        "key_terms_extraction",
        prompt_text,
        validator=make_key_terms_validator(article_body),
        log=log,
    )


def stage_translation(
    english_paragraphs: list[str],
    summary_en: str,
    log: Callable[[str], None],
) -> StageOutcome:
    marked = prompts.format_paragraphs_for_translation(english_paragraphs)
    prompt_text = prompts.render(
        prompts.TRANSLATION_PROMPT,
        paragraph_count=len(english_paragraphs),
        english_paragraphs_marked=marked,
        english_summary=summary_en,
    )
    return run_stage(
        "translation",
        prompt_text,
        validator=make_translation_validator(len(english_paragraphs)),
        log=log,
    )


def stage_quiz(article_body: str, log: Callable[[str], None]) -> StageOutcome:
    prompt_text = prompts.render(
        prompts.QUIZ_GENERATION_PROMPT, article_body=article_body
    )
    return run_stage(
        "quiz_generation",
        prompt_text,
        validator=_validate_quiz,
        log=log,
    )


# =============================================================================
# Article assembly (matches src/lib/articles.ts schema)
# =============================================================================


def assemble_article(
    *,
    topic: dict,
    synthesis_parsed: dict,
    synthesis_outcome: StageOutcome,
    translation_parsed: dict,
    quiz_parsed: dict,
    key_terms_parsed: dict,
    source_articles: list[dict],
    when: datetime,
) -> dict:
    en_paragraphs = split_paragraphs(synthesis_parsed["body"])
    zh_paragraphs = translation_parsed["translated_paragraphs"]

    paragraphs = [
        {"id": f"p{i + 1}", "en": en, "zh": zh}
        for i, (en, zh) in enumerate(zip(en_paragraphs, zh_paragraphs))
    ]

    sources = []
    for sa in source_articles:
        sources.append({
            "name": sa["source"],
            "url": sa["url"],
            "title": sa["title"],
            "publishedAt": sa["published_at"],
        })

    quiz_out = []
    for q in quiz_parsed["questions"]:
        quiz_out.append({
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "options": q["options"],
            "correct": q["correct"],
            "explanationZh": q["explanation_zh"],
        })

    key_terms_out = []
    for kt in (key_terms_parsed.get("key_terms") or []):
        item: dict[str, Any] = {
            "term": kt.get("term", ""),
            "definitionEn": kt.get("definitionEn") or kt.get("definition", ""),
            "definitionZh": kt.get("definitionZh", ""),
        }
        if kt.get("partOfSpeech"):
            item["partOfSpeech"] = kt["partOfSpeech"]
        if kt.get("noteZh"):
            item["noteZh"] = kt["noteZh"]
        key_terms_out.append(item)

    slug = slugify(topic["topic_title"], when)
    date_prefix = when.strftime("%Y-%m-%d")

    return {
        "id": f"{date_prefix}-{slug.rsplit('-', 2)[0]}",
        "slug": slug,
        "publishedAt": when.isoformat().replace("+00:00", "Z"),
        "category": topic["category"],
        "title": synthesis_parsed["title"],
        "subtitle": synthesis_parsed.get("subtitle", "") or None,
        "summary": {
            "en": synthesis_parsed["summary_en"],
            "zh": translation_parsed["translated_summary"],
        },
        "paragraphs": paragraphs,
        "wordCount": int(synthesis_parsed.get("word_count")
                         or len(synthesis_parsed["body"].split())),
        "readingLevel": "B1-B2",
        "keyTerms": key_terms_out,
        "sources": sources,
        "quiz": quiz_out,
        "aiGenerated": True,
        "aiModel": f"{synthesis_outcome.provider}/{synthesis_outcome.model}",
        "aiDisclaimer": "本文由 AI 綜合多家報導生成，事實請以原始來源為準。",
    }


# =============================================================================
# Main pipeline
# =============================================================================


def process_topic(
    topic: dict,
    all_raw: list[dict],
    when: datetime,
    log: Callable[[str], None],
) -> dict | None:
    """Run synthesis → translation → quiz for one topic. Returns final article dict."""
    source_articles = gather_source_articles(topic.get("source_urls", []), all_raw)
    if not source_articles:
        log("  ✗ 該主題沒有任何 source_urls 對應到實際 raw articles，跳過")
        return None

    log(f"  📚 來源：{len(source_articles)} 篇")
    log("  📝 article_synthesis ...")
    synthesis_outcome = stage_article_synthesis(topic, source_articles, log)
    synthesis = synthesis_outcome.parsed
    en_paragraphs = split_paragraphs(synthesis["body"])
    log(f"  ✓ 完成：{synthesis_outcome.duration_sec:.0f}s · "
        f"{synthesis_outcome.tokens_used} tokens · "
        f"字數 {len(synthesis['body'].split())} · {len(en_paragraphs)} 段"
        + ("（fallback）" if synthesis_outcome.fallback_triggered else ""))

    log("  🌐 translation ...")
    translation_outcome = stage_translation(
        en_paragraphs, synthesis["summary_en"], log
    )
    log(f"  ✓ 完成：{translation_outcome.duration_sec:.0f}s · "
        f"段落對齊 {len(en_paragraphs)}={len(translation_outcome.parsed['translated_paragraphs'])}"
        + ("（fallback）" if translation_outcome.fallback_triggered else ""))

    log("  📚 key_terms_extraction ...")
    key_terms_outcome = stage_key_terms_extraction(synthesis["body"], log)
    log(f"  ✓ 完成：{key_terms_outcome.duration_sec:.0f}s · "
        f"{len(key_terms_outcome.parsed.get('key_terms', []))} 個易誤解詞彙"
        + ("（fallback）" if key_terms_outcome.fallback_triggered else ""))

    log("  ❓ quiz_generation ...")
    quiz_outcome = stage_quiz(synthesis["body"], log)
    log(f"  ✓ 完成：{quiz_outcome.duration_sec:.0f}s · "
        f"4 題驗證通過"
        + ("（fallback）" if quiz_outcome.fallback_triggered else ""))

    return assemble_article(
        topic=topic,
        synthesis_parsed=synthesis,
        synthesis_outcome=synthesis_outcome,
        translation_parsed=translation_outcome.parsed,
        quiz_parsed=quiz_outcome.parsed,
        key_terms_parsed=key_terms_outcome.parsed,
        source_articles=source_articles,
        when=when,
    )


def write_article(article: dict, when: datetime) -> Path:
    date_dir = DATA_PUBLISHED / when.strftime("%Y-%m-%d") / "articles"
    date_dir.mkdir(parents=True, exist_ok=True)
    out = date_dir / f"{article['slug']}.json"
    out.write_text(
        json.dumps(article, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def run(args: argparse.Namespace) -> int:
    started = time.monotonic()

    raw_date = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today = (
        datetime.fromisoformat(args.publish_date)
        if args.publish_date
        else datetime.now(timezone.utc)
    )
    if today.tzinfo is None:
        today = today.replace(tzinfo=timezone.utc)

    print(f"📡 Phase 3 — AI 流水線")
    print(f"   來源：data/raw/{raw_date}/headlines.json")
    print(f"   輸出：data/published/{today.strftime('%Y-%m-%d')}/articles/")
    print()

    # Load raw
    try:
        raw = load_raw_articles(raw_date)
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    print(f"✓ 載入 {len(raw)} 篇候選文章")
    print()

    # Stage 1: topic selection
    print("🎯 步驟 1/4：選題（topic_selection）")
    try:
        topic_outcome = stage_topic_selection(raw, log=print)
    except StageFailure as e:
        print(f"\n❌ 選題階段失敗：{e}", file=sys.stderr)
        for h in e.history[-3:]:
            print(f"   - {h['client']} attempt {h['attempt']}: {h['error'][:200]}", file=sys.stderr)
        return 1

    topics = topic_outcome.parsed["selected_topics"]
    print(f"  ✓ 選出 {len(topics)} 個主題（{topic_outcome.duration_sec:.0f}s · "
          f"{topic_outcome.tokens_used} tokens）")
    for i, t in enumerate(topics, 1):
        print(f"    {i}. [{t['category']}] {t['topic_title']} ({len(t.get('source_urls', []))} sources)")

    if args.topic_only:
        print("\n🔧 --topic-only：選題完成，跳過後續階段。")
        return 0

    if args.max_articles is not None:
        topics = topics[: args.max_articles]
        print(f"\n  🔧 --max-articles {args.max_articles}：只處理前 {len(topics)} 個主題")

    # Stages 2-4 per topic
    print()
    successes: list[dict] = []
    failures: list[tuple[dict, str]] = []
    for i, topic in enumerate(topics, 1):
        print(f"[{i}/{len(topics)}] {topic['topic_title']} ({topic['category']})")
        try:
            article = process_topic(topic, raw, today, log=print)
            if article is None:
                failures.append((topic, "no source articles matched"))
                continue
            out_path = write_article(article, today)
            successes.append(article)
            print(f"  💾 寫入 {out_path.relative_to(PROJECT_ROOT)}")
        except StageFailure as e:
            print(f"  ❌ {e}")
            for h in e.history[-2:]:
                print(f"     · {h['client']}: {h['error'][:200]}")
            failures.append((topic, str(e)))
        except Exception as e:
            print(f"  ❌ 未預期錯誤：{e}")
            traceback.print_exc()
            failures.append((topic, str(e)))
        print()

    # Summary
    elapsed = time.monotonic() - started
    print("─" * 60)
    print("📊 完成摘要")
    print("─" * 60)
    print(f"  總耗時：    {elapsed / 60:.1f} 分鐘")
    print(f"  成功：      {len(successes)}/{len(topics)} 篇")
    if failures:
        print(f"  失敗：      {len(failures)} 篇")
        for topic, reason in failures:
            print(f"    · {topic['topic_title']}: {reason[:120]}")
    print()
    if successes:
        print("  本批產出：")
        for a in successes:
            print(f"    [{a['category']}] {a['title']}")
            print(f"      → data/published/{today.strftime('%Y-%m-%d')}/articles/{a['slug']}.json")
    print("─" * 60)
    return 0 if successes else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 3 AI pipeline: synthesize daily articles from raw news."
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Read raw articles from this date's folder (default: today UTC).",
    )
    parser.add_argument(
        "--publish-date",
        default=None,
        help="Publish date used for slug + output folder (default: today UTC).",
    )
    parser.add_argument(
        "--max-articles",
        type=int,
        default=None,
        help="Process at most N topics (useful for first-run verification).",
    )
    parser.add_argument(
        "--topic-only",
        action="store_true",
        help="Stop after topic selection; do not synthesize / translate / quiz.",
    )
    args = parser.parse_args()

    try:
        return run(args)
    except KeyboardInterrupt:
        print("\n⛔ 使用者中斷。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
