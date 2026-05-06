import { useEffect, useState } from "react";
import {
  type BilingualLayout,
  DEFAULT_BILINGUAL_LAYOUT,
  DEFAULT_FONT_SIZE,
  DEFAULT_PRACTICE_MODE,
  type FontSize,
  getBilingualLayout,
  getFontSize,
  getPracticeMode,
  getStats,
  resetAllPreferences,
  setBilingualLayout,
  setFontSize,
  setPracticeMode,
  type Stats,
} from "../lib/preferences";

/**
 * Interactive settings panel rendered inside /settings page.
 *
 * The page itself is statically prerendered by Astro, so this component
 * is a small client island. On mount we read localStorage to sync the
 * UI with whatever the inline init script in BaseLayout already applied
 * to <html>. Updates write through to both localStorage AND the <html>
 * class list — see preferences.ts.
 */
export default function SettingsPanel() {
  // Both default to the same as the inline init script's defaults so the
  // first render (before useEffect runs) matches what the user already sees.
  const [practice, setPractice] = useState(DEFAULT_PRACTICE_MODE);
  const [size, setSize] = useState<FontSize>(DEFAULT_FONT_SIZE);
  const [layout, setLayout] = useState<BilingualLayout>(DEFAULT_BILINGUAL_LAYOUT);
  const [stats, setStats] = useState<Stats | null>(null);
  const [resetConfirm, setResetConfirm] = useState(false);

  // After mount, pull the real values out of localStorage. (We can't do
  // this during render because that would mismatch SSR/static HTML.)
  useEffect(() => {
    setPractice(getPracticeMode());
    setSize(getFontSize());
    setLayout(getBilingualLayout());
    setStats(getStats());
  }, []);

  const handlePracticeToggle = () => {
    const next = !practice;
    setPractice(next);
    setPracticeMode(next);
  };

  const handleSizeChange = (next: FontSize) => {
    setSize(next);
    setFontSize(next);
  };

  const handleLayoutChange = (next: BilingualLayout) => {
    setLayout(next);
    setBilingualLayout(next);
  };

  const handleReset = () => {
    if (!resetConfirm) {
      setResetConfirm(true);
      return;
    }
    resetAllPreferences();
    setPractice(DEFAULT_PRACTICE_MODE);
    setSize(DEFAULT_FONT_SIZE);
    setLayout(DEFAULT_BILINGUAL_LAYOUT);
    setStats(getStats()); // re-pull (now empty) so the stats UI updates
    setResetConfirm(false);
  };

  return (
    <div className="space-y-10">
      {/* ─── Reading preferences ─── */}
      <section>
        <h2 className="text-xl font-semibold mb-1">閱讀偏好</h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mb-5">
          這些設定只儲存在這個瀏覽器，不會同步到其他設備或瀏覽器。
        </p>

        {/* Practice mode toggle */}
        <div className="flex items-start justify-between gap-4 py-4 border-b border-stone-200 dark:border-stone-800">
          <div className="flex-1">
            <div className="font-medium">英文練習模式</div>
            <p className="text-sm text-stone-500 dark:text-stone-400 mt-0.5">
              開啟時：首頁卡片與文章頁的<strong>中文摘要會被隱藏</strong>，
              只顯示英文，避免劇透干擾閱讀練習。
              <br />
              關閉時：中英摘要都會顯示。
              <br />
              <span className="text-xs">（段落對照、易誤解詞彙、Quiz 解析等學習用中文不受影響。）</span>
            </p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={practice}
            onClick={handlePracticeToggle}
            className={`relative inline-flex h-7 w-12 shrink-0 cursor-pointer items-center rounded-full transition-colors ${
              practice
                ? "bg-emerald-500 dark:bg-emerald-600"
                : "bg-stone-300 dark:bg-stone-700"
            }`}
          >
            <span
              className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                practice ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>

        {/* Font size */}
        <div className="py-4 border-b border-stone-200 dark:border-stone-800">
          <div className="font-medium mb-1">內文字體大小</div>
          <p className="text-sm text-stone-500 dark:text-stone-400 mb-3">
            影響文章內段落的字體大小。標題與介面文字不變。
          </p>
          <div className="inline-flex rounded-lg border border-stone-200 dark:border-stone-800 p-1">
            {(["small", "medium", "large"] as const).map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => handleSizeChange(s)}
                className={`px-4 py-1.5 rounded text-sm transition ${
                  size === s
                    ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                    : "text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100"
                }`}
              >
                {s === "small" ? "小" : s === "medium" ? "中" : "大"}
              </button>
            ))}
          </div>
        </div>

        {/* Bilingual layout */}
        <div className="py-4">
          <div className="font-medium mb-1">中英對照排版</div>
          <p className="text-sm text-stone-500 dark:text-stone-400 mb-3">
            在文章內按「中英對照」時，中英段落怎麼擺。只在「中英對照」模式下生效。
          </p>
          <div className="inline-flex rounded-lg border border-stone-200 dark:border-stone-800 p-1">
            <button
              type="button"
              onClick={() => handleLayoutChange("vertical")}
              className={`px-4 py-1.5 rounded text-sm transition ${
                layout === "vertical"
                  ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                  : "text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100"
              }`}
            >
              直式（英上中下）
            </button>
            <button
              type="button"
              onClick={() => handleLayoutChange("responsive")}
              className={`px-4 py-1.5 rounded text-sm transition ${
                layout === "responsive"
                  ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                  : "text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100"
              }`}
            >
              橫式（電腦上左右並排）
            </button>
          </div>
          <p className="mt-2 text-xs text-stone-500 dark:text-stone-400">
            {layout === "vertical"
              ? "目前：所有裝置都直式上下排列。"
              : "目前：手機 / 直式平板自動直式；電腦 / 橫式平板（≥1024px）左右並排。"}
          </p>
        </div>
      </section>

      {/* ─── Learning stats ─── */}
      <section>
        <h2 className="text-xl font-semibold mb-1">學習統計</h2>
        <p className="text-sm text-stone-500 dark:text-stone-400 mb-5">
          只統計這個瀏覽器上的紀錄。文章滾到底部後自動標記為已讀。
        </p>

        {stats === null ? (
          <p className="text-sm text-stone-400 dark:text-stone-500">讀取中…</p>
        ) : stats.totalRead === 0 && stats.quizzesTaken === 0 ? (
          <div className="rounded-lg border border-dashed border-stone-300 dark:border-stone-700 p-6 text-center text-sm text-stone-500 dark:text-stone-400">
            還沒有閱讀紀錄。讀完一篇文章就會出現在這裡。
          </div>
        ) : (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatCard
              label="已讀文章"
              value={stats.totalRead.toString()}
              suffix="篇"
            />
            <StatCard
              label="連續閱讀"
              value={stats.currentStreak.toString()}
              suffix={stats.currentStreak > 0 ? "天 🔥" : "天"}
              hint={
                stats.currentStreak === 0 && stats.lastReadDate
                  ? `上次：${stats.lastReadDate}`
                  : undefined
              }
            />
            <StatCard
              label="最長連續"
              value={stats.longestStreak.toString()}
              suffix="天"
            />
            <StatCard
              label="Quiz 平均"
              value={
                Number.isFinite(stats.quizAvgRatio)
                  ? `${Math.round(stats.quizAvgRatio * 100)}%`
                  : "—"
              }
              hint={
                stats.quizzesTaken > 0
                  ? `共做 ${stats.quizzesTaken} 篇`
                  : "尚未作答"
              }
            />
          </div>
        )}
      </section>

      {/* ─── About ─── */}
      <section>
        <h2 className="text-xl font-semibold mb-3">關於</h2>
        <div className="rounded-lg border border-stone-200 dark:border-stone-800 p-4 space-y-2 text-sm text-stone-700 dark:text-stone-300">
          <p>
            這個網站每天自動產生 4–5 篇 AI 綜合改寫的英文新聞，難度為 CEFR
            B1–B2，適合中文母語者練習英文閱讀。
          </p>
          <p>
            <strong>所有偏好設定（包含閱讀紀錄、Quiz 分數）都儲存在你目前這個瀏覽器，</strong>
            <strong>不會送到任何雲端</strong>，也不會跨設備同步。
          </p>
          <p>
            想看更多介紹（內容怎麼來的、難度設計、新聞來源），請看{" "}
            <a
              href="/about/"
              className="underline text-stone-900 dark:text-stone-100"
            >
              關於本站
            </a>
            頁面。
          </p>
        </div>
      </section>

      {/* ─── Reset ─── */}
      <section>
        <h2 className="text-xl font-semibold mb-3">重置</h2>
        <div className="rounded-lg border border-red-200 dark:border-red-900/40 bg-red-50/50 dark:bg-red-900/10 p-4">
          <p className="text-sm text-stone-700 dark:text-stone-300 mb-3">
            清除這個瀏覽器上儲存的所有偏好設定（練習模式、字體大小，以及未來會新增的閱讀紀錄、Quiz
            分數等）。文章本身不會被刪除。
          </p>
          <button
            type="button"
            onClick={handleReset}
            className={`text-sm px-4 py-2 rounded-md transition ${
              resetConfirm
                ? "bg-red-600 hover:bg-red-700 text-white"
                : "border border-red-300 dark:border-red-800 text-red-700 dark:text-red-400 hover:bg-red-100 dark:hover:bg-red-900/20"
            }`}
          >
            {resetConfirm ? "再按一次確認重置" : "重置所有資料"}
          </button>
          {resetConfirm && (
            <button
              type="button"
              onClick={() => setResetConfirm(false)}
              className="ml-2 text-sm px-4 py-2 rounded-md text-stone-600 dark:text-stone-400 hover:text-stone-900 dark:hover:text-stone-100"
            >
              取消
            </button>
          )}
        </div>
      </section>
    </div>
  );
}

/**
 * Small tile used in the stats grid. Big number on top, label below,
 * optional hint at the bottom.
 */
function StatCard({
  label,
  value,
  suffix,
  hint,
}: {
  label: string;
  value: string;
  suffix?: string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-stone-200 dark:border-stone-800 p-3 text-center">
      <div className="text-2xl font-bold text-stone-900 dark:text-stone-100">
        {value}
        {suffix && (
          <span className="ml-0.5 text-sm font-normal text-stone-500 dark:text-stone-400">
            {suffix}
          </span>
        )}
      </div>
      <div className="text-xs text-stone-500 dark:text-stone-400 mt-1">
        {label}
      </div>
      {hint && (
        <div className="text-[11px] text-stone-400 dark:text-stone-500 mt-0.5">
          {hint}
        </div>
      )}
    </div>
  );
}
