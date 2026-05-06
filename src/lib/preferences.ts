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
