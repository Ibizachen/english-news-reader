import fs from "node:fs";
import path from "node:path";

export const CATEGORIES = [
  "politics",
  "economics",
  "technology",
  "energy",
  "society",
  "health",
  "public-health",
] as const;

export type Category = (typeof CATEGORIES)[number];

export const CATEGORY_LABELS: Record<Category, { en: string; zh: string }> = {
  politics: { en: "Politics", zh: "政治" },
  economics: { en: "Economics", zh: "經濟" },
  technology: { en: "Technology", zh: "科技" },
  energy: { en: "Energy", zh: "能源" },
  society: { en: "Society", zh: "社會" },
  health: { en: "Health", zh: "醫學" },
  "public-health": { en: "Public Health", zh: "公衛" },
};

export interface Paragraph {
  id: string;
  en: string;
  zh: string;
}

export interface KeyTerm {
  term: string;
  /** Optional: "verb", "phrasal verb", "idiom", "noun (here)", etc. */
  partOfSpeech?: string;
  /** Definition in English, in the sense used by this article. */
  definitionEn: string;
  /** 中文解釋，描述此處的意思。 */
  definitionZh: string;
  /** 中文補充說明：為何容易誤解（例：常見為名詞，這裡作動詞）。 */
  noteZh?: string;
}

export interface Source {
  name: string;
  url: string;
  title: string;
  publishedAt: string;
}

export interface PreviousArticle {
  slug: string;
  title: string;
  publishedAt: string;
  category: Category;
  summaryEn?: string;
}

export interface StoryInfo {
  id: string;
  type: "standalone" | "update";
  previousArticles: PreviousArticle[];
}

export interface ArticleSeriesInfo {
  id: string;
  part: number;
  totalParts: number;
}

export type QuizType = "detail" | "inference" | "vocabulary" | "main_idea";

export interface QuizQuestion {
  id: string;
  type: QuizType;
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct: "A" | "B" | "C" | "D";
  explanationZh: string;
}

export interface Article {
  id: string;
  slug: string;
  publishedAt: string;
  category: Category;
  title: string;
  subtitle?: string;
  summary: { en: string; zh: string };
  paragraphs: Paragraph[];
  wordCount: number;
  readingLevel: string;
  keyTerms: KeyTerm[];
  sources: Source[];
  story?: StoryInfo;
  series?: ArticleSeriesInfo;
  quiz: QuizQuestion[];
  aiGenerated: boolean;
  aiModel: string;
  aiDisclaimer: string;
}

// Astro builds always run from the project root, so cwd() gives us a stable base.
const PUBLISHED_DIR = path.join(process.cwd(), "data", "published");

/** Load every published article from data/published/<date>/articles/*.json. */
export function loadArticles(): Article[] {
  const articles: Article[] = [];

  if (!fs.existsSync(PUBLISHED_DIR)) {
    return articles;
  }

  const dateDirs = fs
    .readdirSync(PUBLISHED_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => d.name)
    .sort()
    .reverse();

  for (const date of dateDirs) {
    const articlesDir = path.join(PUBLISHED_DIR, date, "articles");
    if (!fs.existsSync(articlesDir)) continue;

    const files = fs
      .readdirSync(articlesDir)
      .filter((f) => f.endsWith(".json"));

    for (const file of files) {
      const full = path.join(articlesDir, file);
      const raw = fs.readFileSync(full, "utf-8");
      try {
        const article = JSON.parse(raw) as Article;
        articles.push(article);
      } catch (err) {
        console.error(`Failed to parse article ${full}:`, err);
      }
    }
  }

  articles.sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));

  return articles;
}

export function getArticleBySlug(slug: string): Article | undefined {
  return loadArticles().find((a) => a.slug === slug);
}

export function getArticlesByCategory(category: Category): Article[] {
  return loadArticles().filter((a) => a.category === category);
}

// Force Taipei timezone for all human-facing date / time display so the
// site doesn't depend on the build host's local timezone (Cloudflare builds
// on UTC servers, but our audience reads in Asia/Taipei).
const DISPLAY_TZ = "Asia/Taipei";

/** Get the YYYY-MM-DD date string in DISPLAY_TZ. Used for grouping articles. */
export function getLocalDate(iso: string): string {
  // Swedish locale produces YYYY-MM-DD format reliably across browsers.
  return new Date(iso).toLocaleDateString("sv-SE", { timeZone: DISPLAY_TZ });
}

export function formatDate(iso: string, locale: "en" | "zh" = "en"): string {
  const d = new Date(iso);
  if (locale === "zh") {
    return new Intl.DateTimeFormat("zh-TW", {
      year: "numeric",
      month: "long",
      day: "numeric",
      timeZone: DISPLAY_TZ,
    }).format(d);
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    timeZone: DISPLAY_TZ,
  }).format(d);
}

/** Date + time including AM/PM in 中文 (e.g. "2026年5月6日 上午5:51"). */
export function formatDateTime(iso: string, locale: "en" | "zh" = "en"): string {
  const d = new Date(iso);
  if (locale === "zh") {
    return new Intl.DateTimeFormat("zh-TW", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZone: DISPLAY_TZ,
    }).format(d);
  }
  return new Intl.DateTimeFormat("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZone: DISPLAY_TZ,
  }).format(d);
}
