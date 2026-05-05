"""
fetch_news.py — Phase 2 news fetcher for the English Reading Practice site.

Reads scripts/sources.yaml, fetches each RSS feed, then for every entry that
was published within the lookback window it downloads the article and runs
trafilatura to extract the main body text. Output goes to:

    data/raw/YYYY-MM-DD/headlines.json     <-- list of all articles
    data/raw/YYYY-MM-DD/articles/<sha1>.json   <-- one file per article

A failure on any single source is reported and skipped, never aborts the
overall run.

Usage:
    uv run python scripts/fetch_news.py                  # full run, 24h window
    uv run python scripts/fetch_news.py --dry-run        # only test RSS
    uv run python scripts/fetch_news.py --window 48      # widen lookback to 48h
    uv run python scripts/fetch_news.py --limit 5        # cap entries per source
    uv run python scripts/fetch_news.py --date 2026-05-06 # override output dir
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import httpx
import trafilatura
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = PROJECT_ROOT / "scripts" / "sources.yaml"
DATA_RAW = PROJECT_ROOT / "data" / "raw"

DEFAULT_ENTRIES_PER_SOURCE = 30
DEFAULT_WINDOW_HOURS = 24
CONCURRENT_LIMIT = 8       # max simultaneous article fetches
HTTP_TIMEOUT = 30.0
MIN_ARTICLE_CHARS = 400    # below this, drop the article (likely a stub/blurb)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
    "EnglishNewsReader/0.1 (+personal-learning-project)"
)


# ---------- Data models ----------


@dataclass
class RawArticle:
    """A single news article fetched from a source, ready for the AI pipeline."""

    title: str
    url: str
    source: str
    category_hints: list[str]
    published_at: str  # ISO 8601 in UTC, e.g. "2026-05-06T08:00:00Z"
    full_text: str
    word_count: int


@dataclass
class SourceResult:
    """The outcome of fetching one source — used for the summary table."""

    name: str
    rss_ok: bool = True
    rss_error: str | None = None
    rss_entries: int = 0
    entries_in_window: int = 0
    articles_extracted: int = 0
    articles_failed: int = 0


# ---------- Helpers ----------


def status_line(text: str, status: str = "info") -> str:
    icon = {"ok": "✓", "fail": "✗", "info": "·", "warn": "!"}.get(status, "·")
    return f"  {icon} {text}"


def parse_entry_published(entry: Any) -> datetime | None:
    """Pull a UTC datetime from a feedparser entry. Returns None if absent."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        ts = getattr(entry, key, None)
        if ts is None and isinstance(entry, dict):
            ts = entry.get(key)
        if ts:
            try:
                return datetime(*ts[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                continue
    return None


def entry_url(entry: Any) -> str | None:
    """Extract the article URL from a feedparser entry."""
    link = getattr(entry, "link", None)
    if link:
        return link
    links = getattr(entry, "links", None) or []
    for l in links:
        href = l.get("href") if isinstance(l, dict) else None
        if href:
            return href
    return None


def entry_title(entry: Any) -> str:
    return str(getattr(entry, "title", "") or "").strip()


# ---------- Async fetchers ----------


async def fetch_rss(
    client: httpx.AsyncClient, source: dict, limit: int
) -> tuple[list[Any], str | None]:
    """Fetch one RSS feed; return (entries, error_or_None)."""
    try:
        resp = await client.get(
            source["rss"], timeout=HTTP_TIMEOUT, follow_redirects=True
        )
        resp.raise_for_status()
    except httpx.TimeoutException:
        return [], "timeout"
    except httpx.HTTPStatusError as e:
        return [], f"HTTP {e.response.status_code}"
    except httpx.HTTPError as e:
        return [], type(e).__name__
    except Exception as e:
        return [], f"{type(e).__name__}: {e}"

    parsed = feedparser.parse(resp.content)
    entries = list(parsed.entries[:limit])
    if not entries and parsed.bozo:
        return [], "feed parse error"
    return entries, None


async def fetch_article_text(
    client: httpx.AsyncClient, semaphore: asyncio.Semaphore, url: str
) -> str | None:
    """Download an article URL and extract the main body text."""
    async with semaphore:
        try:
            resp = await client.get(
                url, timeout=HTTP_TIMEOUT, follow_redirects=True
            )
            resp.raise_for_status()
        except Exception:
            return None
        html = resp.text
        final_url = str(resp.url)

    try:
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            url=final_url,
        )
    except Exception:
        return None

    if not text or len(text) < MIN_ARTICLE_CHARS:
        return None
    return text.strip()


# ---------- Main pipeline ----------


async def run(args: argparse.Namespace) -> int:
    started = time.monotonic()

    if not SOURCES_FILE.exists():
        print(f"❌ 找不到設定檔：{SOURCES_FILE}", file=sys.stderr)
        return 1

    cfg = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))
    sources: list[dict] = cfg.get("sources", []) or []
    if not sources:
        print(f"❌ {SOURCES_FILE} 裡沒有任何來源", file=sys.stderr)
        return 1

    today = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = DATA_RAW / today
    articles_dir = out_dir / "articles"
    articles_dir.mkdir(parents=True, exist_ok=True)

    cutoff = datetime.now(timezone.utc) - timedelta(hours=args.window)

    print(f"📡 載入 {len(sources)} 個新聞來源（{SOURCES_FILE.relative_to(PROJECT_ROOT)}）")
    print(f"⏰ 過濾條件：發布時間在過去 {args.window} 小時內")
    print(f"📂 輸出目錄：{out_dir.relative_to(PROJECT_ROOT)}/")
    print()

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    async with httpx.AsyncClient(headers=headers, http2=False) as client:
        # ---- Step 1: fetch all RSS feeds in parallel ----
        print(f"🔍 步驟 1/2：抓取 {len(sources)} 個 RSS feeds ...")
        rss_results = await asyncio.gather(
            *(fetch_rss(client, s, args.limit) for s in sources)
        )

        source_results: list[SourceResult] = []
        candidates: list[tuple[dict, Any, datetime, str]] = []
        for source, (entries, err) in zip(sources, rss_results):
            sr = SourceResult(name=source["name"], rss_ok=err is None, rss_error=err)
            sr.rss_entries = len(entries)

            for entry in entries:
                pub = parse_entry_published(entry)
                if not pub or pub < cutoff:
                    continue
                url = entry_url(entry)
                if not url:
                    continue
                candidates.append((source, entry, pub, url))
                sr.entries_in_window += 1

            source_results.append(sr)

            if err:
                print(status_line(f"{source['name']:<38} 失敗：{err}", "fail"))
            else:
                print(status_line(
                    f"{source['name']:<38} {sr.rss_entries:>3} 篇 RSS · "
                    f"{sr.entries_in_window:>3} 篇在 {args.window}h 內",
                    "ok",
                ))

        ok_sources = sum(1 for sr in source_results if sr.rss_ok)
        print()
        print(f"📊 RSS 步驟結果：成功 {ok_sources}/{len(sources)} 個來源，"
              f"共有 {len(candidates)} 篇候選文章")

        if args.dry_run:
            print()
            print("🔧 --dry-run：跳過全文擷取，結束。")
            return 0

        if not candidates:
            print()
            print("⚠️ 沒有任何文章符合過濾條件。請檢查網路或拉長 --window 看看。")
            return 0

        # ---- Step 2: dedup + extract full text ----
        seen: set[str] = set()
        unique_candidates: list[tuple[dict, Any, datetime, str]] = []
        for c in candidates:
            url = c[3]
            if url in seen:
                continue
            seen.add(url)
            unique_candidates.append(c)

        if (dups := len(candidates) - len(unique_candidates)) > 0:
            print(f"🔁 去除重複網址：跳過 {dups} 篇")

        print()
        print(f"📰 步驟 2/2：擷取 {len(unique_candidates)} 篇全文 "
              f"（最多 {CONCURRENT_LIMIT} 個並行連線，預估 1-3 分鐘）...")

        semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
        text_results = await asyncio.gather(
            *(fetch_article_text(client, semaphore, url)
              for (_, _, _, url) in unique_candidates),
            return_exceptions=True,
        )

        articles: list[RawArticle] = []
        sr_by_name = {sr.name: sr for sr in source_results}
        for (source, entry, pub, url), result in zip(unique_candidates, text_results):
            sr = sr_by_name[source["name"]]
            if isinstance(result, Exception) or not result:
                sr.articles_failed += 1
                continue
            article = RawArticle(
                title=entry_title(entry),
                url=url,
                source=source["name"],
                category_hints=source.get("categories", []) or [],
                published_at=pub.isoformat().replace("+00:00", "Z"),
                full_text=result,
                word_count=len(result.split()),
            )
            articles.append(article)
            sr.articles_extracted += 1

        # ---- Save ----
        headlines_path = out_dir / "headlines.json"
        headlines_path.write_text(
            json.dumps([asdict(a) for a in articles], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        for article in articles:
            sha = hashlib.sha1(article.url.encode("utf-8")).hexdigest()
            (articles_dir / f"{sha}.json").write_text(
                json.dumps(asdict(article), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    elapsed = time.monotonic() - started
    total_failed = sum(sr.articles_failed for sr in source_results)

    print()
    print("─" * 60)
    print("📊 完成摘要")
    print("─" * 60)
    print(f"  耗時：              {elapsed:.1f} 秒")
    print(f"  成功 RSS 來源：     {ok_sources}/{len(sources)}")
    print(f"  全文擷取成功：      {len(articles)} 篇")
    print(f"  全文擷取失敗：      {total_failed} 篇")
    print()

    cat_counts: dict[str, int] = {}
    for a in articles:
        for cat in a.category_hints:
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
    if cat_counts:
        print("  各分類分布（依來源 hints；一篇可同時屬於多類）：")
        for cat in sorted(cat_counts.keys()):
            print(f"    {cat:<18} {cat_counts[cat]:>3} 篇")
        print()

    print(f"  輸出：")
    print(f"    {headlines_path.relative_to(PROJECT_ROOT)}")
    print(f"    {articles_dir.relative_to(PROJECT_ROOT)}/  (個別 JSON 檔)")
    print("─" * 60)

    if len(articles) < 50:
        print()
        print("⚠️ 擷取數量低於 SPEC §4 Phase 2 的目標（50+）。")
        print("   可能原因：當天新聞較少、部分來源網站擋爬蟲、或某些 RSS 暫時失效。")
        print("   重跑或拉長 --window 通常能解決。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Phase 2 news fetcher (RSS + article extraction)."
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_ENTRIES_PER_SOURCE,
        help=f"Max RSS entries per source (default: {DEFAULT_ENTRIES_PER_SOURCE}).",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=DEFAULT_WINDOW_HOURS,
        help=f"Lookback window in hours (default: {DEFAULT_WINDOW_HOURS}).",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Override output date (YYYY-MM-DD). Defaults to today UTC.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only fetch RSS feeds; skip full-article extraction.",
    )
    args = parser.parse_args()

    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        print("\n⛔ 使用者中斷。", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
