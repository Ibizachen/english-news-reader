/**
 * User preferences stored in localStorage. Keys are namespaced under
 * `enr.*` (English News Reader) so they don't collide with anything else
 * the browser might be storing for this domain.
 *
 * The inline script in BaseLayout.astro reads these values BEFORE first
 * paint to avoid a flash of wrong content. Anything in this file runs
 * later (after hydration) and updates both localStorage and the <html>
 * class list to keep them in sync.
 *
 * All functions are safe to call on the server (where `window` doesn't
 * exist) — they no-op and return defaults.
 */
export type FontSize = "small" | "medium" | "large";

/**
 * Bilingual paragraph layout when "中英對照" mode is on:
 *   - "vertical":  English on top, Chinese below (always, every screen size).
 *                  Better for reading flow — you read EN first, then check ZH.
 *   - "responsive": Stack on small screens, side-by-side on desktop (≥1024px).
 *                   The original behavior. Some readers prefer it.
 */
export type BilingualLayout = "vertical" | "responsive";

export const STORAGE_KEYS = {
  practiceMode: "enr.practiceMode",
  fontSize: "enr.fontSize",
  bilingualLayout: "enr.bilingualLayout",
  read: "enr.read",
  scores: "enr.scores",
} as const;

export const DEFAULT_PRACTICE_MODE = true;
export const DEFAULT_FONT_SIZE: FontSize = "medium";
export const DEFAULT_BILINGUAL_LAYOUT: BilingualLayout = "vertical";

const isBrowser = typeof window !== "undefined";

/* ─── Practice mode ────────────────────────────────────────────── */

export function getPracticeMode(): boolean {
  if (!isBrowser) return DEFAULT_PRACTICE_MODE;
  try {
    const v = localStorage.getItem(STORAGE_KEYS.practiceMode);
    // Default = ON unless explicitly "false".
    return v !== "false";
  } catch {
    return DEFAULT_PRACTICE_MODE;
  }
}

export function setPracticeMode(on: boolean): void {
  if (!isBrowser) return;
  try {
    localStorage.setItem(STORAGE_KEYS.practiceMode, on ? "true" : "false");
  } catch {
    // Silently ignore — user may be in private mode.
  }
  document.documentElement.classList.toggle("practice-mode", on);
}

/* ─── Font size ────────────────────────────────────────────────── */

export function getFontSize(): FontSize {
  if (!isBrowser) return DEFAULT_FONT_SIZE;
  try {
    const v = localStorage.getItem(STORAGE_KEYS.fontSize);
    if (v === "small" || v === "large") return v;
    return DEFAULT_FONT_SIZE;
  } catch {
    return DEFAULT_FONT_SIZE;
  }
}

export function setFontSize(size: FontSize): void {
  if (!isBrowser) return;
  try {
    localStorage.setItem(STORAGE_KEYS.fontSize, size);
  } catch {
    // ignore
  }
  const root = document.documentElement;
  root.classList.remove("text-small", "text-medium", "text-large");
  root.classList.add(`text-${size}`);
}

/* ─── Bilingual layout ─────────────────────────────────────────── */

export function getBilingualLayout(): BilingualLayout {
  if (!isBrowser) return DEFAULT_BILINGUAL_LAYOUT;
  try {
    const v = localStorage.getItem(STORAGE_KEYS.bilingualLayout);
    if (v === "responsive") return "responsive";
    return DEFAULT_BILINGUAL_LAYOUT;
  } catch {
    return DEFAULT_BILINGUAL_LAYOUT;
  }
}

export function setBilingualLayout(layout: BilingualLayout): void {
  if (!isBrowser) return;
  try {
    localStorage.setItem(STORAGE_KEYS.bilingualLayout, layout);
  } catch {
    // ignore
  }
  document.documentElement.classList.toggle(
    "bilingual-responsive",
    layout === "responsive",
  );
}

/* ─── Read tracking ────────────────────────────────────────────── */

/**
 * Map of article slug → ISO timestamp of FIRST time this device finished
 * reading it (= scrolled past the article body). Re-reading does NOT
 * overwrite — we only record the first read so streaks stay meaningful.
 */
export type ReadDict = Record<string, string>;

export function getReadDict(): ReadDict {
  if (!isBrowser) return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.read);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

export function isRead(slug: string): boolean {
  const dict = getReadDict();
  return Boolean(dict[slug]);
}

/** Records the article as read. No-op if already recorded. */
export function markRead(slug: string): void {
  if (!isBrowser || !slug) return;
  try {
    const dict = getReadDict();
    if (dict[slug]) return; // already recorded — keep first-read timestamp
    dict[slug] = new Date().toISOString();
    localStorage.setItem(STORAGE_KEYS.read, JSON.stringify(dict));
  } catch {
    // ignore
  }
}

/* ─── Quiz scores ──────────────────────────────────────────────── */

export interface QuizScore {
  correct: number;
  total: number;
  takenAt: string; // ISO timestamp
}

export type QuizScoreDict = Record<string, QuizScore>;

export function getQuizScores(): QuizScoreDict {
  if (!isBrowser) return {};
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.scores);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

/**
 * Records quiz score for an article. Latest attempt overwrites earlier.
 */
export function saveQuizScore(
  slug: string,
  correct: number,
  total: number,
): void {
  if (!isBrowser || !slug) return;
  try {
    const dict = getQuizScores();
    dict[slug] = { correct, total, takenAt: new Date().toISOString() };
    localStorage.setItem(STORAGE_KEYS.scores, JSON.stringify(dict));
  } catch {
    // ignore
  }
}

/* ─── Streak / stats ───────────────────────────────────────────── */

const READING_TZ = "Asia/Taipei";

/** Convert ISO timestamp to YYYY-MM-DD in Taipei time. */
function toTaipeiDate(iso: string): string {
  return new Date(iso).toLocaleDateString("sv-SE", { timeZone: READING_TZ });
}

/** Returns YYYY-MM-DD `n` days from `dateStr` (UTC arithmetic). */
function shiftDate(dateStr: string, days: number): string {
  const d = new Date(dateStr + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export interface Stats {
  totalRead: number;
  currentStreak: number;
  longestStreak: number;
  quizzesTaken: number;
  /** Average correct ratio across attempted quizzes, in 0..1. NaN if none. */
  quizAvgRatio: number;
  /** ISO date (YYYY-MM-DD) of last reading day, or null. */
  lastReadDate: string | null;
}

export function getStats(): Stats {
  const reads = getReadDict();
  const scores = getQuizScores();

  const slugs = Object.keys(reads);
  const totalRead = slugs.length;

  // Unique reading dates (Taipei) sorted ascending.
  const dateSet = new Set<string>();
  for (const iso of Object.values(reads)) dateSet.add(toTaipeiDate(iso));
  const dates = Array.from(dateSet).sort();

  let longestStreak = 0;
  let currentStreak = 0;
  let lastReadDate: string | null = null;

  if (dates.length > 0) {
    lastReadDate = dates[dates.length - 1];

    // Longest streak across all of history.
    let run = 1;
    longestStreak = 1;
    for (let i = 1; i < dates.length; i++) {
      if (shiftDate(dates[i - 1], 1) === dates[i]) {
        run++;
        if (run > longestStreak) longestStreak = run;
      } else {
        run = 1;
      }
    }

    // Current streak: only counts if the most recent reading day is today
    // or yesterday (Taipei) — otherwise the streak has been broken.
    const today = toTaipeiDate(new Date().toISOString());
    const yesterday = shiftDate(today, -1);
    if (lastReadDate === today || lastReadDate === yesterday) {
      currentStreak = 1;
      let cursor = lastReadDate;
      for (let i = dates.length - 2; i >= 0; i--) {
        if (shiftDate(dates[i], 1) === cursor) {
          currentStreak++;
          cursor = dates[i];
        } else {
          break;
        }
      }
    }
  }

  const scoreList = Object.values(scores);
  const quizzesTaken = scoreList.length;
  const quizAvgRatio =
    quizzesTaken === 0
      ? NaN
      : scoreList.reduce((sum, s) => sum + s.correct / s.total, 0) /
        quizzesTaken;

  return {
    totalRead,
    currentStreak,
    longestStreak,
    quizzesTaken,
    quizAvgRatio,
    lastReadDate,
  };
}

/* ─── Reset all preferences ────────────────────────────────────── */

/** Removes every `enr.*` key from localStorage. */
export function resetAllPreferences(): void {
  if (!isBrowser) return;
  try {
    const toRemove: string[] = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith("enr.")) toRemove.push(key);
    }
    toRemove.forEach((k) => localStorage.removeItem(k));
  } catch {
    // ignore
  }
  // Apply defaults visually so user sees the reset took effect.
  setPracticeMode(DEFAULT_PRACTICE_MODE);
  setFontSize(DEFAULT_FONT_SIZE);
  setBilingualLayout(DEFAULT_BILINGUAL_LAYOUT);
}
