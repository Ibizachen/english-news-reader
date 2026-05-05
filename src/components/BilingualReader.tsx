import { useEffect, useState } from "react";

type Paragraph = { id: string; en: string; zh: string };

type Mode = "en" | "bilingual";

const STORAGE_KEY = "reading-mode";

interface Props {
  paragraphs: Paragraph[];
}

export default function BilingualReader({ paragraphs }: Props) {
  const [mode, setMode] = useState<Mode>("en");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved === "bilingual" || saved === "en") setMode(saved);
    } catch {
      // ignore
    }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try {
      window.localStorage.setItem(STORAGE_KEY, mode);
    } catch {
      // ignore
    }
  }, [mode, hydrated]);

  const isBilingual = mode === "bilingual";

  return (
    <div>
      <div className="mb-6 flex flex-wrap items-center gap-3 border-b border-stone-200 dark:border-stone-800 pb-3">
        <span className="text-sm text-stone-500 dark:text-stone-400">
          閱讀模式 ·
        </span>
        <div className="inline-flex rounded-md border border-stone-300 dark:border-stone-700 overflow-hidden">
          <button
            type="button"
            onClick={() => setMode("en")}
            className={
              "px-3 py-1.5 text-sm transition " +
              (!isBilingual
                ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                : "bg-white text-stone-700 hover:bg-stone-50 dark:bg-stone-950 dark:text-stone-300 dark:hover:bg-stone-900")
            }
            aria-pressed={!isBilingual}
          >
            純英文 · English only
          </button>
          <button
            type="button"
            onClick={() => setMode("bilingual")}
            className={
              "px-3 py-1.5 text-sm transition border-l border-stone-300 dark:border-stone-700 " +
              (isBilingual
                ? "bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900"
                : "bg-white text-stone-700 hover:bg-stone-50 dark:bg-stone-950 dark:text-stone-300 dark:hover:bg-stone-900")
            }
            aria-pressed={isBilingual}
          >
            中英對照 · Bilingual
          </button>
        </div>
      </div>

      <div className="space-y-6">
        {paragraphs.map((p) => (
          <Paragraph key={p.id} para={p} bilingual={isBilingual} />
        ))}
      </div>
    </div>
  );
}

function Paragraph({
  para,
  bilingual,
}: {
  para: Paragraph;
  bilingual: boolean;
}) {
  if (!bilingual) {
    return (
      <p className="text-stone-800 dark:text-stone-200 leading-[1.85] text-[1.05rem]">
        {para.en}
      </p>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 lg:gap-6">
      <p className="text-stone-800 dark:text-stone-200 leading-[1.85] text-[1.05rem]">
        {para.en}
      </p>
      <p className="rounded-md bg-stone-50 dark:bg-stone-900 p-3 lg:p-0 lg:bg-transparent lg:dark:bg-transparent text-stone-700 dark:text-stone-300 leading-[1.9] text-[1rem]">
        {para.zh}
      </p>
    </div>
  );
}
