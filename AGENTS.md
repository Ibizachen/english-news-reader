# AGENTS.md

> **Audience:** AI coding assistants (Codex, Cursor, Aider, Claude Code, etc.)
> **Purpose:** Onboard you to this project in 2 minutes. Read this BEFORE doing anything else.

---

## What this project is

A daily English news reading practice site for Traditional-Chinese-speaking learners, built solo by a non-programmer with AI assistance. Every day at 06:13 Taipei time the pipeline:

1. Fetches headlines from 30+ RSS feeds (BBC, Guardian, NPR, The Conversation, Lancet, CDC MMWR, EurekAlert, etc.).
2. Uses Gemini API to pick **6** substantive topics, synthesize 600-1000 word B1-B2 English articles, translate paragraph-by-paragraph into Traditional Chinese, extract tricky vocabulary, and generate 4-question quizzes.
3. Commits the resulting JSON to `data/published/<UTC-date>/articles/<slug>.json`.
4. Cloudflare Pages auto-rebuilds the Astro static site.

- **Live site:** https://english-news-reader.pages.dev
- **Repo:** https://github.com/Ibizachen/english-news-reader
- **License & host:** Public repo · Cloudflare Pages (free) · GitHub Actions (free tier) · Gemini free tier

## About the owner (READ THIS — it changes how you communicate)

- Programming experience: **zero**, actively learning.
- Native language: **Traditional Chinese (繁體中文)**. Always reply in 繁中.
- Setup: MacBook Pro, macOS, zsh, home directory `/Users/ibizachen`.
- Owns: Cloudflare account, GitHub account (`Ibizachen`), Gemini API key.
- **Communication style she prefers:**
  - One step at a time — don't dump 10 commands.
  - For each step explain: **what** it does, **why** this way, what **success** looks like, how to tell if it **failed**.
  - Don't assume technical jargon — explain in passing as you use it.
  - Lead with the concept, then the command. She wants to understand, not copy-paste blindly.

## Tech stack

| Layer            | Tools                                                                                   |
|------------------|-----------------------------------------------------------------------------------------|
| Frontend         | Astro 6 (`output: "static"`), React 19 islands, Tailwind 4, TypeScript strict           |
| Pipeline         | Python 3.11+, uv, feedparser, trafilatura, httpx                                        |
| AI               | Gemini 3.1 Flash Lite Preview (primary, 500 RPD) + Gemini 2.5 Flash (fallback, 20 RPD)  |
| Hosting          | Cloudflare Pages (static), GitHub Actions (daily cron)                                  |
| External cron    | Cloudflare Workers Cron Trigger (because GitHub Actions schedule is unreliable)         |
| Search           | Pagefind (build-time static index, fully client-side)                                   |
| State            | `localStorage` only — no backend, no accounts, no DB                                    |

## Repository structure

```
nm-claude-code-ver/
├── src/                              # Astro frontend
│   ├── pages/                        # Each .astro = a URL
│   │   ├── index.astro               # Homepage (today + last 7 days + browse)
│   │   ├── archive.astro             # /archive page 1
│   │   ├── archive/page/[page].astro # /archive/page/N (20 per page)
│   │   ├── articles/[slug].astro     # Article detail
│   │   ├── category/[category].astro # Category page 1
│   │   ├── category/[category]/page/[page].astro
│   │   ├── search.astro              # Pagefind UI
│   │   ├── settings.astro            # User preferences
│   │   ├── about.astro
│   │   └── admin/, api/              # Local-only (excluded from prod build)
│   ├── components/                   # Astro + React components
│   │   ├── BilingualReader.tsx       # English/Chinese paragraph reader
│   │   ├── Quiz.tsx                  # 4-question MCQ with score persistence
│   │   ├── SettingsPanel.tsx         # Settings UI (React island)
│   │   ├── ArticleCard.astro         # Card with engagement ✓ indicator
│   │   └── Header.astro              # Nav, search/settings icons
│   ├── layouts/BaseLayout.astro      # Shared shell + inline preference scripts
│   ├── lib/articles.ts               # Article types + loader from data/published/
│   ├── lib/preferences.ts            # localStorage helpers (enr.* keys)
│   └── styles/global.css             # Tailwind + custom rules
├── scripts/                          # Python pipeline
│   ├── fetch_news.py                 # Phase 2: RSS → data/raw/<date>/headlines.json
│   ├── ai_pipeline.py                # Phase 3: 5-stage orchestrator
│   ├── prompts.py                    # All 5 AI prompts (topic / synthesis / translation / key_terms / quiz)
│   ├── llm_client.py                 # Gemini / Ollama / Anthropic abstraction
│   ├── sources.yaml                  # 30+ RSS feed list with category hints
│   └── ai_config.yaml                # Default pipeline config (Ollama-based; cloud overrides)
├── data/
│   ├── raw/<date>/headlines.json     # Fetched headlines (gitignored)
│   └── published/<UTC-date>/articles/<slug>.json  # Final articles (committed)
├── .github/workflows/daily.yml       # GitHub Actions pipeline (cron unreliable; see gotchas)
├── cloudflare-worker/                # External cron trigger
│   ├── cron-trigger.js               # Worker that calls GitHub workflow dispatch API
│   └── README.md                     # Setup steps
├── bin/build_for_deploy.sh           # Cloudflare build (excludes admin/api, runs Pagefind)
└── docs (root): README, CHANGELOG, OPERATIONS, SPEC, PHASE3_ADDENDUM, this file
```

## Read these next (in priority order)

1. **`README.md`** — project overview, current status, quick start.
2. **`CHANGELOG.md`** — every version v1.0 → v2.4 with what changed and **why**. This is the project's running design journal.
3. **`OPERATIONS.md`** — comprehensive maintenance guide: daily flow, 9 maintenance SOPs, 5 troubleshooting scenarios.
4. **`SPEC.md`** — original requirements doc (some details have evolved; CHANGELOG is the source of truth for current behavior).
5. **`PHASE3_ADDENDUM.md`** — Phase 3 robustness design (citation validation, paragraph alignment, etc.).
6. **`cloudflare-worker/README.md`** — external cron trigger setup.

## Critical gotchas (non-obvious things that will trip you up)

### 1. GitHub Actions `schedule:` does NOT fire for this repo

After 4 cron configurations across 24+ hours, the GitHub Actions `schedule:` trigger fired **zero** times. The Cloudflare Worker in `cloudflare-worker/cron-trigger.js` is the **primary** scheduled trigger — it calls GitHub's `workflows/{id}/dispatches` API daily at 06:13 Taipei (= 22:13 UTC).

We left the `schedule:` block in `daily.yml` in case GitHub eventually wakes up; if both fire on the same day, you'll get duplicate articles (acceptable but annoying — fix by commenting out the GitHub schedule).

### 2. Article folders use UTC date, not Taipei date

The Python pipeline writes to `data/published/<UTC-date>/articles/`. An article generated at 06:13 Taipei = 22:13 UTC the previous day, so it lands in *yesterday's* UTC folder. The frontend displays via `Intl.DateTimeFormat` with `timeZone: "Asia/Taipei"`, so the user-facing date is correct. **Don't try to "fix" this by switching to local-date folders** — it would break sorting.

### 3. Translation requires Taiwan-style transliterations

The translation prompt in `scripts/prompts.py` explicitly forces:

| Required (Taiwan) | NOT (Mainland)        |
|-------------------|-----------------------|
| 川普               | 特朗普                 |
| 馬克宏             | 馬克龍                 |
| 荷莫茲             | 霍爾木茲               |
| 普京               | 普丁                   |
| 拜登               | 拜登 (same — kept)    |
| 歐巴馬             | 奧巴馬                 |
| 雪梨               | 悉尼                   |

Do not soften this. Audience is Taiwan.

### 4. Gemini `thinking_budget=0` is mandatory

Without it, Gemini 2.5 Flash consumes all output tokens on internal reasoning and returns empty/truncated JSON. Set in `scripts/llm_client.py` (`GeminiClient`).

### 5. Practice mode (English-only) is ON by default

This is the **core design philosophy**: English-first reading practice with Chinese as on-demand reference. The homepage cards in practice mode show only title + English subtitle; the Chinese summary returns only when the user explicitly turns practice mode OFF at `/settings`. Bilingual paragraph reader defaults to vertical (English on top, Chinese below) — also user-configurable.

Do **not** add Chinese content that violates the default English-first experience.

### 6. `localStorage` schema (`enr.*` keys)

| Key                    | Type                                  | Purpose                                          |
|------------------------|---------------------------------------|--------------------------------------------------|
| `enr.practiceMode`     | `"true"` / `"false"`                  | English practice mode toggle (default ON)        |
| `enr.fontSize`         | `"small"` / `"medium"` / `"large"`    | Article body font size                           |
| `enr.bilingualLayout`  | `"vertical"` / `"responsive"`         | Bilingual reader layout                          |
| `enr.visited`          | `{ [slug]: ISO timestamp }`           | Pages user has loaded (→ gray ✓)                |
| `enr.read`             | `{ [slug]: ISO timestamp }`           | Articles scrolled to bottom (→ feeds streak)    |
| `enr.scores`           | `{ [slug]: {correct,total,takenAt} }` | Quiz results                                     |

"Engaged" (green ✓ on card) = `enr.read[slug]` AND `enr.scores[slug]`. "Visited" (gray ✓) = page opened (or legacy `enr.read` data).

### 7. Pre-paint inline script avoids FOUC

`BaseLayout.astro` injects a small inline `<script>` in `<head>` that reads localStorage and applies CSS classes (`practice-mode`, `text-{size}`, `bilingual-responsive`) on `<html>` BEFORE first paint. Don't break this — it prevents flash of wrong content.

### 8. Astro `paginate()` scoping quirk

`getStaticPaths()` runs in an isolated scope and **cannot** see frontmatter module-level consts. If you use `PAGE_SIZE` (or similar) in both `getStaticPaths` and the rendered template, declare it twice (keep the values in sync). See `src/pages/archive/page/[page].astro` for the pattern.

### 9. `data/config/ai_settings.json` is gitignored

Local dev uses `scripts/ai_config.yaml` defaults. Cloud builds (`daily.yml`) write `ai_settings.json` inline with the cloud-appropriate config (Gemini-only, with fallback chain). The admin UI also writes here; never commit this file.

### 10. Pagination URL pattern

Page 1 lives at the canonical URL: `/archive/`, `/category/politics/`. Pages 2+ at `/archive/page/2/`, `/category/politics/page/2/`. **Always 20 per page**. See existing files for the convention.

## Conventions

- **Timezone:** `Asia/Taipei` for all human-facing dates/times (use `Intl.DateTimeFormat` with `timeZone`).
- **Reading level:** CEFR B1–B2. The strict vocabulary list lives in `ARTICLE_SYNTHESIS_PROMPT` in `prompts.py`.
- **Categories:** 7 — `politics`, `economics`, `technology`, `energy`, `society`, `health`, `public-health`. (TCM was dropped in v2.3.0.)
- **Daily output:** 6 articles.
- **Versioning:** SemVer with git tags (`git tag -a v2.X.Y`). The CHANGELOG is the source of truth for what each version did.
- **Commit style:** Imperative title (under 72 chars), body explains the WHY, not the WHAT (the diff already shows WHAT).
- **Don't auto-`git push`:** Always show the user the diff and let them decide. Pushing modifies the live site within minutes.

## What NOT to do

- ❌ Don't add a backend, database, or accounts system — staticness is core.
- ❌ Don't trigger workflows with PII — there are no users in any sense.
- ❌ Don't scrape news sites directly — only use legal RSS feeds in `sources.yaml`.
- ❌ Don't fabricate news citations — `_check_citations()` in `ai_pipeline.py` rejects mentions of outlets not in `article.sources`. If you change this, you're inviting hallucination.
- ❌ Don't modify Asia/Taipei timezone displays — Taiwan-targeted site.
- ❌ Don't bump daily article count past ~10 — would risk exceeding Gemini free quota; current value (6) has 95% margin.
- ❌ Don't restore TCM — there isn't enough English-language coverage to populate it.
- ❌ Don't make Chinese the default on cards — practice mode default is a product decision, not laziness.

## Useful commands

```bash
# Local dev — admin / api work; Pagefind search doesn't (index lives in dist/)
npm run dev

# Production build (Cloudflare runs this; admin/api excluded; Pagefind index generated)
bash bin/build_for_deploy.sh

# Run pipeline locally (requires GEMINI_API_KEY env var)
uv run python scripts/fetch_news.py
uv run python scripts/ai_pipeline.py

# Manually trigger today's article generation
gh workflow run daily.yml

# View recent workflow runs
gh run list --workflow=daily.yml --limit 5

# Tag a release
git tag -a v2.X.Y -m "v2.X.Y — summary"
git push origin v2.X.Y
```

## Current version

**v2.4.0** as of 2026-05-07. See `CHANGELOG.md` for the full history (v1.0.0 through v2.4.0).

Major themes by version:
- **v2.0.0** — Practice mode + settings page + vertical bilingual layout
- **v2.1.0** — Read tracking + quiz scores + streak + learning stats
- **v2.2.0** — Full-text search via Pagefind
- **v2.3.0** — Content expansion (6/day, 10 new RSS, drop TCM) + pagination
- **v2.4.0** — Two-state engagement (gray ✓ visited / green ✓ engaged); Quiz before Words to Watch

## When asked to do something, ask yourself

1. **Is there a CHANGELOG entry for similar work?** The owner's design instincts are documented there. Match the philosophy.
2. **Does this break "static, free, no-backend, English-first"?** If yes, push back before implementing.
3. **Did you read OPERATIONS.md first?** If the request is operational (cron failed, no articles today, quota exceeded), the answer is probably already there.
4. **Are you about to commit something the owner can't read?** Use clear comments, plain naming, and write the commit message in a way she can verify.

Welcome aboard. Be a good co-author.
