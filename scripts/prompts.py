"""
prompts.py — Prompt templates for the four AI pipeline stages.

These follow SPEC §8 and PHASE3_ADDENDUM §5 (validation requirements).

Templates use {placeholder} syntax. Use render(template, **kwargs) — it does a
simple string replace so the literal `{` and `}` in JSON examples don't need
to be doubled the way `str.format()` would require.
"""

from __future__ import annotations

from typing import Any


def render(template: str, **kwargs: Any) -> str:
    """Substitute {key} placeholders. Plain text replacement (no escaping needed for JSON)."""
    out = template
    for key, value in kwargs.items():
        out = out.replace("{" + key + "}", str(value))
    return out


# =============================================================================
# 1. Topic selection (SPEC §8.1)
# =============================================================================

TOPIC_SELECTION_PROMPT = """
You are a news editor selecting today's topics for an English reading practice site.

Review the headlines below, organized by category. Select 6 topics that meet ALL of these criteria:
1. Cover at least 4 different categories (politics, economics, technology, energy, society, health, public-health)
   — explicitly TRY to include at least one health AND one public-health topic if reasonable candidates exist
2. Are SUBSTANTIVE — avoid celebrity gossip, sports scores, weather, minor accidents
3. Have multiple independent sources covering them (cluster headlines about the same story when you can)
4. Have clear cause-and-effect or multi-perspective angles
5. Would be interesting to an intermediate (CEFR B1-B2) English learner

For each selected topic, identify 3-5 source URLs from the headlines list to use as raw material.
If only 1-2 sources cover a topic, that's still acceptable — just pick the best available.

Headlines (format per line: [SOURCE] title — url):
{headlines_block}

Output as valid JSON, nothing else. No markdown fences, no preamble:
{
  "selected_topics": [
    {
      "topic_title": "Short topic name (max 8 words)",
      "category": "politics|economics|technology|energy|society|health|public-health",
      "rationale": "One sentence on why this topic and angle",
      "source_urls": ["url1", "url2", "url3"]
    }
  ]
}
""".strip()


def format_headlines_for_topic_selection(headlines: list[dict[str, Any]]) -> str:
    """Group headlines by primary category hint and format as a single text block.

    Each headline is a dict with keys: title, source, url, category_hints.
    """
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for h in headlines:
        hints = h.get("category_hints") or ["other"]
        cat = hints[0]
        by_cat.setdefault(cat, []).append(h)

    lines: list[str] = []
    for cat in sorted(by_cat.keys()):
        lines.append("")
        lines.append(f"=== {cat.upper()} ===")
        for h in by_cat[cat]:
            title = (h.get("title") or "").replace("\n", " ").strip()
            if len(title) > 220:
                title = title[:217] + "..."
            url = h.get("url") or ""
            source = h.get("source") or "?"
            lines.append(f"[{source}] {title} — {url}")
    return "\n".join(lines).strip()


# =============================================================================
# 2. Article synthesis (SPEC §8.2 — updated for tricky-vocabulary key_terms)
# =============================================================================

ARTICLE_SYNTHESIS_PROMPT = """
You are an expert journalist writing for English language learners at CEFR B1-B2 level.

Synthesize a SINGLE long-form news article from the source materials below.

REQUIREMENTS:
- Length: 600-1000 words. Count carefully; staying in this range is mandatory.

**VOCABULARY LEVEL — STRICT B1-B2:**
- Target CEFR B1-B2. Use COMMON, FREQUENTLY-USED words that a Taiwanese high-school graduate would recognise.
- AVOID rare, literary, academic, or journalistic-flair vocabulary unless ABSOLUTELY necessary. When in doubt, swap to a simpler word.
- Examples to AVOID (and what to use instead):
  * "brinkmanship" → "risky standoff" / "dangerous game of pressure"
  * "barrage" → "wave of" / "series of"
  * "intolerable" → "unacceptable" / "very hard to accept"
  * "unilateral" → "one-sided" / "without agreement from others"
  * "ablaze" → "on fire" / "burning"
  * "stranded" → "stuck" / "unable to leave"
  * "ascertain" → "find out"
  * "exacerbate" → "make worse"
  * "leverage (verb)" → "use to gain advantage"
  * "rhetoric" → "language" / "wording"
- If a specialised term is genuinely required (e.g. "ceasefire", "sanctions", "vaccine"), briefly explain it on FIRST use in plain words (e.g. "a ceasefire — an agreement to stop fighting").
- The "key_terms" section below is where TRICKY words go for explicit teaching. Don't pad the article with rare words just so you can put them in key_terms.

- Sentence structure: Mostly simple-to-medium. Occasional complex sentences are fine but don't overdo it.
- Depth: Despite simple wording, cover the topic SUBSTANTIVELY. Include:
  * Background / why this matters
  * Current situation
  * Multiple perspectives or stakeholder views
  * Implications or what might come next
- Citation style: Throughout the article, attribute claims to specific sources using natural news-writing phrases:
  * "According to <SOURCE>, ..."
  * "<SOURCE> reports that ..."
  * "<SOURCE> noted ..."
  * "<SOURCE> cited a senior official saying ..."
  CRITICAL RULES for citations:
  * <SOURCE> MUST be one of the source outlets explicitly listed in the input source materials block. DO NOT invent attributions to outlets that don't appear in the input (no fake "Reuters", "AP", "NYT" citations).
  * Every outlet you cite must end up in `sources_used`.
  * If you can't find which input source supports a claim, paraphrase without attribution instead of fabricating one.

- Factual care: Do NOT invent specific facts that aren't in the source materials.
  * Place names: when describing geographic relationships, prefer general phrasing ("expensive areas including X and Y") over specific spatial claims ("around X" / "near X" / "outside X") unless the spatial claim is supported by the input.
  * Numbers, dates, names of people: only use what's actually in the sources. If a number isn't stated, paraphrase ("rose sharply") instead of inventing a figure.
  * If sources disagree, note the disagreement rather than picking a side.

- Tone: Neutral, factual, balanced. Do not editorialize.
- Structure: Compelling lead → background → current development → multiple angles → outlook
- Output the article in clearly separated paragraphs (use \\n\\n between paragraphs). At least 4 paragraphs.

(NOTE: The "易誤解詞彙 / key terms" section is generated by a SEPARATE downstream stage that sees ONLY the article body you write here. Don't worry about producing key_terms in this output.)

Topic: {topic_title}
Category: {category}

Source materials (each preceded by [SOURCE_N - source_name]):

{source_articles_block}

Output as valid JSON, nothing else. No markdown fences, no preamble:
{
  "title": "Engaging article title",
  "subtitle": "Optional one-line subtitle that adds nuance",
  "summary_en": "Five sentences summarizing the article.",
  "body": "Full article body, paragraphs separated by \\n\\n",
  "word_count": 847,
  "sources_used": ["BBC News", "The Guardian"]
}
""".strip()


def format_source_articles_for_synthesis(source_articles: list[dict[str, Any]]) -> str:
    """Format source articles as labeled blocks for the synthesis prompt.

    Each source is a dict with: title, source, url, full_text.
    Truncate each article body if it's very long (LLM context budget).
    """
    blocks: list[str] = []
    for i, art in enumerate(source_articles, 1):
        source = art.get("source", "?")
        title = (art.get("title") or "").strip()
        url = art.get("url") or ""
        text = (art.get("full_text") or "").strip()
        # Cap each source at ~3500 chars (~600 words) to stay within context.
        if len(text) > 3500:
            text = text[:3500] + "\n[...truncated...]"
        blocks.append(
            f"[SOURCE_{i} - {source}]\n"
            f"Title: {title}\n"
            f"URL: {url}\n\n"
            f"{text}"
        )
    return "\n\n---\n\n".join(blocks)


# =============================================================================
# 3. Translation (SPEC §8.3)
# =============================================================================

TRANSLATION_PROMPT = """
You are a professional translator. Translate the following English news article into Traditional Chinese (繁體中文) for Taiwanese readers learning English.

REQUIREMENTS:
- Translate paragraph by paragraph. The number of output paragraphs MUST EXACTLY EQUAL the number of input paragraphs.
- One Chinese paragraph per English paragraph, in the same order. DO NOT merge or split paragraphs.
- Use natural, fluent Chinese. Avoid translation-ese (避免翻譯腔).

**CRITICAL — NO ENGLISH IN THE BODY:**
- Output 100% Traditional Chinese in the translated body. Do NOT leave any English word untranslated.
- If a word resists direct translation (e.g. "counterpart"), PARAPHRASE it in Chinese. Never copy the English word into the Chinese text.
- The ONLY exception: on the FIRST mention of a proper noun (person / place / organisation name), you MAY include the English in parentheses for reference, like 「馬克宏 (Emmanuel Macron)」. Skip the English on second mention.
- Do not include English in parentheses for words that are obvious or already well-known to Taiwanese readers (e.g. don't write 「美國 (USA)」; don't write 「總統 (President)」).

**TAIWAN-STANDARD TRANSLITERATIONS (this is mandatory, not optional):**
- Always use Taiwan media's transliteration of proper nouns, NOT mainland Chinese. Examples:
  * Strait of Hormuz → 荷莫茲海峽 (NOT 荷爾木茲、NOT 霍爾木茲)
  * Donald Trump → 川普 (NOT 特朗普)
  * Emmanuel Macron → 馬克宏 (NOT 馬克龍)
  * Vladimir Putin → 普丁 (NOT 普京)
  * Volodymyr Zelensky → 澤倫斯基 (NOT 泽连斯基)
  * Joe Biden → 拜登
  * Xi Jinping → 習近平
  * Kim Jong-un → 金正恩
  * Benjamin Netanyahu → 納坦雅胡 (NOT 内塔尼亚胡)
  * Recep Tayyip Erdoğan → 艾爾段 (NOT 埃尔多安)
  * Volodymyr → 澤倫斯基的姓名不轉成簡體
- For Chinese internet / vocabulary differences:
  * 「資訊」not「信息」、「影片」not「視頻」、「網路」not「網絡」、「軟體」not「軟件」、「列印」not「打印」、「滑鼠」not「鼠標」
- When uncertain about a name, default to how Taiwan media (中央社, 自由時報, 聯合報, BBC 中文 Taiwan) renders it. Better to omit the English parenthetical than guess wrong.

**OTHER:**
- Preserve attribution phrases naturally: "According to Reuters" → 「根據路透社報導」; "BBC reports that" → 「BBC 報導」; "AP cited a senior official saying" → 「美聯社引述一位資深官員的話」.
- Translate the summary too.

Input has {paragraph_count} English paragraphs (separated by [PARA] markers below). Your output MUST have exactly {paragraph_count} translated paragraphs.

English article:

{english_paragraphs_marked}

English summary:
{english_summary}

Output as valid JSON, nothing else. No markdown fences, no preamble:
{
  "translated_paragraphs": ["第一段翻譯", "第二段翻譯", "第三段翻譯", "..."],
  "translated_summary": "中文摘要（對應英文摘要的內容）"
}
""".strip()


# =============================================================================
# 5. Key-terms extraction (independent stage, runs AFTER article synthesis)
# =============================================================================
# Why a separate stage: when key_terms is produced inside article_synthesis,
# the LLM has both the (rare-vocabulary) source materials AND the (simplified)
# synthesized article in context. It often quotes example sentences from the
# source materials, which then don't appear in the simplified article — the
# website shows broken example references. By isolating this stage to ONLY the
# synthesized body, every quoted example must come from text actually shown
# to the reader.

KEY_TERMS_EXTRACTION_PROMPT = """
You are an English vocabulary teacher creating a "tricky words" callout for a CEFR B1-B2 reading practice site (Taiwanese audience).

INPUT: ONE finalised English article (already simplified, will not change).
TASK: Pick 3-5 TRICKY words or phrases that ACTUALLY APPEAR in the article body below.

PRIORITISE these kinds of words:
- Used in a non-literal / metaphorical sense (e.g. "stalled" for talks, "cooled" for spending)
- Used in an UNCOMMON part of speech (e.g. "frame" as a verb, "split" as a noun, "block" as a verb)
- Phrasal verbs / idioms whose meaning is NOT obvious from the parts (e.g. "drop out", "line up", "outweigh", "wiped out")
- Words that look easy but mean something specific in this context

AVOID:
- Words explained inside the article body itself (those don't need a callout)
- Pure specialised terms (technical jargon) that the article already defines

For each pick, you MUST include:
- "term": the word or phrase as it appears in the article (use the form that appears in the article)
- "partOfSpeech": e.g. "verb", "phrasal verb", "noun (here)", "idiom"
- "definitionEn": English definition in THIS article's sense
- "definitionZh": 繁體中文定義（台灣用語）
- "noteZh": 中文補充，說明為何容易被誤讀（例：常見作名詞，這裡作動詞），並用「文中：」帶出文中出現該詞的句子。

⚠️ ABSOLUTELY CRITICAL — quote ONLY from the article body below:
- The English sentence you quote in `noteZh` (after 「文中：」) MUST be copy-pasted character-for-character from the article body below. Do NOT paraphrase it. Do NOT use any other source.
- If you cannot find the word used in a sentence you can quote verbatim, DROP that word and pick a different one. Better to output 3 verified entries than 5 with fabricated quotes.
- If you can only find 2 good entries, output 2. Do not pad.

Article body:

{article_body}

Output as valid JSON, nothing else. No markdown fences, no preamble:
{
  "key_terms": [
    {
      "term": "frame",
      "partOfSpeech": "verb",
      "definitionEn": "To describe something in a chosen way to influence how people see it.",
      "definitionZh": "把某件事描述成某種樣子，藉此影響別人怎麼看它。",
      "noteZh": "常見作名詞（畫框），這裡作動詞用。文中：state media framed the move as a response."
    }
  ]
}
""".strip()


# =============================================================================
# Helper for translation prompt
# =============================================================================


def format_paragraphs_for_translation(paragraphs: list[str]) -> str:
    """Mark each paragraph with [PARA n/N] so the LLM can count.

    Returns a single string. Splits with double newlines and explicit markers.
    """
    n = len(paragraphs)
    marked = []
    for i, p in enumerate(paragraphs, 1):
        marked.append(f"[PARA {i}/{n}]\n{p.strip()}")
    return "\n\n".join(marked)


# =============================================================================
# 4. Quiz generation (SPEC §8.4)
# =============================================================================

QUIZ_GENERATION_PROMPT = """
You are an English reading comprehension quiz designer for intermediate (CEFR B1-B2) learners.

Create EXACTLY 4 multiple choice questions based on the article below. The 4 questions MUST cover these 4 distinct types in this order:

1. DETAIL: Test recall of a specific fact stated in the article. Should require careful reading, not just keyword spotting.
2. INFERENCE: Require connecting information across paragraphs to reach a conclusion not directly stated.
3. VOCABULARY IN CONTEXT: Pick a moderately challenging word from the article and ask its meaning AS USED in context. Prefer words used non-literally or in unusual parts of speech.
4. MAIN IDEA: Test overall understanding of the article's central argument or message.

For each question:
- Provide 4 options (A, B, C, D)
- Exactly one is clearly correct
- The 3 distractors should be PLAUSIBLE — testing common misreadings, not absurd
- Provide a DETAILED explanation in Traditional Chinese (繁體中文，台灣用語) that:
  * Explains WHY the correct answer is right (with specific paragraph reference)
  * Explains WHY each of the 3 wrong answers is wrong
  * Total length at least 80 Chinese characters

Article:

{article_body}

Output as valid JSON, nothing else. No markdown fences, no preamble:
{
  "questions": [
    {
      "id": "q1",
      "type": "detail",
      "question": "Question text in English",
      "options": {"A": "...", "B": "...", "C": "...", "D": "..."},
      "correct": "B",
      "explanation_zh": "正確答案 B，因為文章第三段明確提到...。選項 A 不對，因為...。選項 C 是常見誤讀，因為...。選項 D 雖然提到了，但不是問題問的重點..."
    },
    {"id": "q2", "type": "inference", "question": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct": "C", "explanation_zh": "..."},
    {"id": "q3", "type": "vocabulary", "question": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct": "A", "explanation_zh": "..."},
    {"id": "q4", "type": "main_idea", "question": "...", "options": {"A": "...", "B": "...", "C": "...", "D": "..."}, "correct": "D", "explanation_zh": "..."}
  ]
}
""".strip()
