import { useEffect, useMemo, useState } from "react";

const PROVIDERS = ["ollama", "claude", "gemini", "openrouter"] as const;
type Provider = (typeof PROVIDERS)[number];

const PROVIDER_LABELS: Record<Provider, string> = {
  ollama: "Ollama（本地）",
  claude: "Anthropic Claude（付費）",
  gemini: "Google Gemini（免費 tier）",
  openrouter: "OpenRouter（聚合）",
};

const STAGE_KEYS = [
  "topic_selection",
  "article_synthesis",
  "translation",
  "key_terms_extraction",
  "quiz_generation",
] as const;
type Stage = (typeof STAGE_KEYS)[number];

const STAGE_META: Record<Stage, { zh: string; en: string; desc: string; emoji: string }> = {
  topic_selection: {
    emoji: "🎯",
    zh: "選題",
    en: "Topic Selection",
    desc: "從候選新聞挑出今天要寫的 4-5 個主題",
  },
  article_synthesis: {
    emoji: "📝",
    zh: "文章合成",
    en: "Article Synthesis",
    desc: "把 3-5 篇來源綜合成 600-1000 字英文新聞（最吃英文寫作品質）",
  },
  translation: {
    emoji: "🌐",
    zh: "翻譯",
    en: "Translation",
    desc: "英文段落 → 繁體中文段落（段對段）",
  },
  key_terms_extraction: {
    emoji: "📚",
    zh: "易誤解詞彙",
    en: "Key Terms Extraction",
    desc: "從合成後的英文文章挑 3-5 個易誤讀詞（獨立階段，只看簡化文章）",
  },
  quiz_generation: {
    emoji: "❓",
    zh: "出題",
    en: "Quiz Generation",
    desc: "4 題選擇題 + 中文解析",
  },
};

const HARDCODED_MODELS: Record<Provider, string[]> = {
  ollama: [], // populated dynamically
  claude: [
    "claude-opus-4-7",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
  ],
  gemini: ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
  openrouter: [
    "anthropic/claude-sonnet-4.6",
    "anthropic/claude-opus-4.7",
    "google/gemini-2.5-flash",
    "google/gemini-2.5-pro",
    "openai/gpt-4o",
    "meta-llama/llama-3.3-70b-instruct",
  ],
};

// =====================================================================
// Quick presets — clicked once to fill the form, still need 💾 儲存.
// =====================================================================

interface Preset {
  id: string;
  emoji: string;
  zh: string;
  desc: string;
  build: () => Record<Stage, StageConfig>;
}

const ollamaStage = (extra: Partial<StageConfig> = {}): StageConfig => ({
  provider: "ollama",
  model: "qwen3.6:35b-a3b",
  temperature: 0.4,
  max_tokens: 4000,
  fallback: { provider: "gemini", model: "gemini-2.5-flash" },
  ...extra,
});

const geminiStage = (
  fallback: FallbackConfig | undefined,
  extra: Partial<StageConfig> = {}
): StageConfig => ({
  provider: "gemini",
  model: "gemini-2.5-flash",
  temperature: 0.4,
  max_tokens: 4000,
  fallback,
  ...extra,
});

// Note on max_tokens: Gemini Flash in JSON mode emits heavily-indented output
// which inflates output token usage 30-50%. We pad token budgets accordingly
// so JSON doesn't get truncated mid-string.
const FLASH_FALLBACK: FallbackConfig = { provider: "gemini", model: "gemini-2.0-flash" };

const PRESETS: Preset[] = [
  {
    id: "local",
    emoji: "🏠",
    zh: "本地優先",
    desc: "全部 Ollama 跑本地，備援 Gemini Flash。電腦插電 + Ollama 跑得動時用，省 Gemini 配額。",
    build: () => ({
      topic_selection: ollamaStage({ temperature: 0.3, max_tokens: 4000 }),
      article_synthesis: ollamaStage({ temperature: 0.4, max_tokens: 6000 }),
      translation: ollamaStage({ temperature: 0.2, max_tokens: 6000 }),
      key_terms_extraction: ollamaStage({ temperature: 0.3, max_tokens: 3000 }),
      quiz_generation: ollamaStage({ temperature: 0.5, max_tokens: 4000 }),
    }),
  },
  {
    id: "hybrid",
    emoji: "⚡",
    zh: "混合（推薦）",
    desc: "合成 + 出題用 Gemini（品質好），選題 + 翻譯用 Ollama（Qwen3 中文強）。日常用這個。",
    build: () => ({
      topic_selection: ollamaStage({ temperature: 0.3, max_tokens: 4000 }),
      article_synthesis: geminiStage(
        { provider: "ollama", model: "qwen3.6:35b-a3b" },
        { temperature: 0.4, max_tokens: 6000 }
      ),
      translation: ollamaStage({ temperature: 0.2, max_tokens: 6000 }),
      key_terms_extraction: geminiStage(
        { provider: "ollama", model: "qwen3.6:35b-a3b" },
        { temperature: 0.3, max_tokens: 3000 }
      ),
      quiz_generation: geminiStage(
        { provider: "ollama", model: "qwen3.6:35b-a3b" },
        { temperature: 0.5, max_tokens: 4000 }
      ),
    }),
  },
  {
    id: "cloud",
    emoji: "🌐",
    zh: "外出模式",
    desc: "全部 Gemini Flash，備援 Gemini 2.0（避免單一模型 503 時整個爆掉）。電腦在外面、沒電、不跑本地時用。",
    build: () => ({
      topic_selection: geminiStage(FLASH_FALLBACK, { temperature: 0.3, max_tokens: 4000 }),
      article_synthesis: geminiStage(FLASH_FALLBACK, { temperature: 0.4, max_tokens: 6000 }),
      translation: geminiStage(FLASH_FALLBACK, { temperature: 0.2, max_tokens: 6000 }),
      key_terms_extraction: geminiStage(FLASH_FALLBACK, { temperature: 0.3, max_tokens: 3000 }),
      quiz_generation: geminiStage(FLASH_FALLBACK, { temperature: 0.5, max_tokens: 4000 }),
    }),
  },
];

interface FallbackConfig {
  provider: Provider;
  model: string;
}

interface StageConfig {
  provider: Provider;
  model: string;
  temperature: number;
  max_tokens: number;
  fallback?: FallbackConfig;
}

interface AiSettings {
  ai_pipeline: Record<Stage, StageConfig>;
  global: {
    json_retry_max: number;
    stage_failure_isolation: boolean;
    cost_cap_usd_per_run: number;
  };
}

interface EnvStatus {
  ollama: boolean;
  gemini: boolean;
  claude: boolean;
  openrouter: boolean;
}

interface Props {
  initialSettings: AiSettings;
  initiallyUsingDefaults: boolean;
}

const DEEP_CLONE = (x: unknown) => JSON.parse(JSON.stringify(x));

/** Compare current AI settings against a preset's stages. Returns true if every
 *  stage's primary + fallback exactly matches the preset. */
function settingsMatchPreset(
  settings: AiSettings,
  preset: Preset
): boolean {
  const built = preset.build();
  for (const stage of STAGE_KEYS) {
    const cur = settings.ai_pipeline[stage];
    const want = built[stage];
    if (!cur || !want) return false;
    if (cur.provider !== want.provider) return false;
    if (cur.model !== want.model) return false;
    if (cur.temperature !== want.temperature) return false;
    if (cur.max_tokens !== want.max_tokens) return false;
    const fbA = cur.fallback;
    const fbB = want.fallback;
    if (!fbA && !fbB) continue;
    if (!fbA || !fbB) return false;
    if (fbA.provider !== fbB.provider) return false;
    if (fbA.model !== fbB.model) return false;
  }
  return true;
}

export default function SettingsForm({
  initialSettings,
  initiallyUsingDefaults,
}: Props) {
  const [settings, setSettings] = useState<AiSettings>(initialSettings);
  const [usingDefaults, setUsingDefaults] = useState(initiallyUsingDefaults);
  const [ollamaModels, setOllamaModels] = useState<string[]>([]);
  const [ollamaError, setOllamaError] = useState<string | null>(null);
  const [envStatus, setEnvStatus] = useState<EnvStatus>({
    ollama: true,
    gemini: false,
    claude: false,
    openrouter: false,
  });
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState<Record<Stage, boolean>>({
    topic_selection: false,
    article_synthesis: false,
    translation: false,
    key_terms_extraction: false,
    quiz_generation: false,
  });

  // Detect which preset (if any) the current settings exactly match.
  const activePresetId = useMemo(() => {
    for (const p of PRESETS) {
      if (settingsMatchPreset(settings, p)) return p.id;
    }
    return null;
  }, [settings]);
  const activePreset = PRESETS.find((p) => p.id === activePresetId) ?? null;

  // Initial fetches
  useEffect(() => {
    fetch("/api/ollama-models")
      .then((r) => r.json())
      .then((d) => {
        if (d.ok) {
          setOllamaModels(d.models);
        } else {
          setOllamaError(d.error || "無法連到 Ollama");
        }
      })
      .catch((e) => setOllamaError(String(e)));
    fetch("/api/env-status")
      .then((r) => r.json())
      .then(setEnvStatus)
      .catch(() => {});
  }, []);

  const modelsFor = (provider: Provider): string[] => {
    if (provider === "ollama") {
      return ollamaModels.length > 0 ? ollamaModels : ["qwen3.6:35b-a3b"];
    }
    return HARDCODED_MODELS[provider];
  };

  const updateStage = (stage: Stage, patch: Partial<StageConfig>) => {
    setSettings((prev) => {
      const next: AiSettings = DEEP_CLONE(prev);
      next.ai_pipeline[stage] = { ...next.ai_pipeline[stage], ...patch };
      // If provider changed, snap model to first option of new provider
      if (patch.provider && !modelsFor(patch.provider).includes(next.ai_pipeline[stage].model)) {
        next.ai_pipeline[stage].model = modelsFor(patch.provider)[0] || "";
      }
      return next;
    });
    setDirty(true);
    setSaveMsg(null);
  };

  const updateFallback = (stage: Stage, patch: Partial<FallbackConfig> | null) => {
    setSettings((prev) => {
      const next: AiSettings = DEEP_CLONE(prev);
      if (patch === null) {
        delete next.ai_pipeline[stage].fallback;
      } else {
        const current = next.ai_pipeline[stage].fallback || {
          provider: "gemini" as Provider,
          model: "gemini-2.5-flash",
        };
        const updated = { ...current, ...patch };
        if (patch.provider && !modelsFor(patch.provider).includes(updated.model)) {
          updated.model = modelsFor(patch.provider)[0] || "";
        }
        next.ai_pipeline[stage].fallback = updated;
      }
      return next;
    });
    setDirty(true);
    setSaveMsg(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg(null);
    try {
      const resp = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(settings),
      });
      const data = await resp.json();
      if (data.ok) {
        setDirty(false);
        setUsingDefaults(false);
        setSaveMsg(`✅ 已儲存 (${new Date().toLocaleTimeString()})`);
      } else {
        setSaveMsg(`❌ 儲存失敗：${data.error}`);
      }
    } catch (err) {
      setSaveMsg(`❌ 錯誤：${err}`);
    } finally {
      setSaving(false);
    }
  };

  const applyPreset = (preset: Preset) => {
    if (
      dirty &&
      !window.confirm(
        `套用「${preset.zh}」會覆蓋目前未儲存的變更，繼續？`
      )
    ) {
      return;
    }
    setSettings((prev) => ({
      ...prev,
      ai_pipeline: preset.build(),
    }));
    setDirty(true);
    setSaveMsg(`📋 已套用「${preset.zh}」— 記得按「💾 儲存設定」`);
  };

  const handleReset = async () => {
    if (
      !window.confirm(
        "確定要重設為預設值？\n這會刪除 data/config/ai_settings.json，下次跑 pipeline 會改用 scripts/ai_config.yaml 的預設值。"
      )
    )
      return;
    try {
      const resp = await fetch("/api/settings", { method: "DELETE" });
      const data = await resp.json();
      if (data.ok) {
        setSaveMsg("🔄 已重設為預設值，重新整理頁面以載入");
        setTimeout(() => window.location.reload(), 800);
      } else {
        setSaveMsg(`❌ 重設失敗：${data.error}`);
      }
    } catch (err) {
      setSaveMsg(`❌ 錯誤：${err}`);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button
          type="button"
          onClick={handleSave}
          disabled={saving || !dirty}
          className="px-5 py-2 rounded-md bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition"
        >
          {saving ? "儲存中…" : "💾 儲存設定"}
        </button>
        <button
          type="button"
          onClick={handleReset}
          className="px-4 py-2 rounded-md border border-stone-300 dark:border-stone-700 hover:bg-stone-50 dark:hover:bg-stone-900 transition"
        >
          🔄 重設為預設
        </button>
        {dirty && !saving && (
          <span className="text-xs text-amber-600 dark:text-amber-400">未儲存的變更</span>
        )}
        {saveMsg && <span className="text-xs">{saveMsg}</span>}
      </div>

      <section className="rounded-lg border border-stone-200 dark:border-stone-800 p-4">
        <div className="flex items-baseline gap-2 mb-3 flex-wrap">
          <h2 className="text-base font-semibold">快速組合</h2>
          {activePreset ? (
            <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">
              · 目前使用：{activePreset.emoji} {activePreset.zh}
            </span>
          ) : (
            <span className="text-xs text-stone-500 dark:text-stone-400">
              · 目前是自訂組合（不對應任何 preset）
            </span>
          )}
          <span className="text-xs text-stone-500 dark:text-stone-400 ml-auto">
            點按鈕只更新表單，記得按「💾 儲存設定」才會生效
          </span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          {PRESETS.map((p) => {
            const isActive = activePresetId === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => applyPreset(p)}
                className={[
                  "text-left rounded-md border p-3 transition relative",
                  isActive
                    ? "border-emerald-500 dark:border-emerald-500 bg-emerald-50/60 dark:bg-emerald-900/20 ring-2 ring-emerald-500/30"
                    : "border-stone-200 dark:border-stone-800 hover:border-stone-400 dark:hover:border-stone-600 hover:bg-stone-50 dark:hover:bg-stone-900",
                ].join(" ")}
              >
                {isActive && (
                  <span className="absolute top-2 right-2 text-[10px] font-medium px-1.5 py-0.5 rounded bg-emerald-600 text-white">
                    ✓ 使用中
                  </span>
                )}
                <div className="font-semibold text-sm pr-14">
                  {p.emoji} {p.zh}
                </div>
                <div className="mt-1 text-xs text-stone-600 dark:text-stone-400 leading-relaxed">
                  {p.desc}
                </div>
              </button>
            );
          })}
        </div>
      </section>

      {ollamaError && (
        <div className="rounded-md border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-900 dark:text-amber-200">
          ⚠️ 無法列出本機 Ollama 模型：{ollamaError}
          <div className="text-xs mt-1 text-amber-800 dark:text-amber-300">
            設定仍可儲存，但下拉選單只會顯示 <code>qwen3.6:35b-a3b</code>。請確認 Ollama 應用程式正在執行。
          </div>
        </div>
      )}

      {STAGE_KEYS.map((stage) => (
        <StageCard
          key={stage}
          stage={stage}
          config={settings.ai_pipeline[stage]}
          modelsFor={modelsFor}
          envStatus={envStatus}
          advancedOpen={advancedOpen[stage]}
          setAdvancedOpen={(v) => setAdvancedOpen((p) => ({ ...p, [stage]: v }))}
          updateStage={updateStage}
          updateFallback={updateFallback}
        />
      ))}

      <details className="rounded-md border border-stone-200 dark:border-stone-800 p-4 text-sm">
        <summary className="cursor-pointer font-medium">全域設定 · Global</summary>
        <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <label className="block">
            <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
              JSON 解析失敗最多重試
            </div>
            <input
              type="number"
              min={1}
              max={10}
              value={settings.global.json_retry_max}
              onChange={(e) => {
                setSettings((prev) => ({
                  ...prev,
                  global: { ...prev.global, json_retry_max: Number(e.target.value) },
                }));
                setDirty(true);
              }}
              className="w-full px-2 py-1 rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-950"
            />
          </label>
          <label className="block">
            <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">
              文章層級失敗隔離
            </div>
            <select
              value={String(settings.global.stage_failure_isolation)}
              onChange={(e) => {
                setSettings((prev) => ({
                  ...prev,
                  global: {
                    ...prev.global,
                    stage_failure_isolation: e.target.value === "true",
                  },
                }));
                setDirty(true);
              }}
              className="w-full px-2 py-1 rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-950"
            >
              <option value="true">啟用（建議）</option>
              <option value="false">關閉</option>
            </select>
          </label>
        </div>
      </details>

      <div className="text-xs text-stone-500 dark:text-stone-400 border-t border-stone-200 dark:border-stone-800 pt-4">
        <strong>狀態：</strong>
        {usingDefaults
          ? "使用 scripts/ai_config.yaml 預設值（還沒儲存過自訂設定）"
          : "使用 data/config/ai_settings.json"}
        {activePreset && (
          <span className="ml-1">
            — 對應「{activePreset.emoji} {activePreset.zh}」組合
          </span>
        )}
      </div>
    </div>
  );
}

function StageCard({
  stage,
  config,
  modelsFor,
  envStatus,
  advancedOpen,
  setAdvancedOpen,
  updateStage,
  updateFallback,
}: {
  stage: Stage;
  config: StageConfig;
  modelsFor: (p: Provider) => string[];
  envStatus: EnvStatus;
  advancedOpen: boolean;
  setAdvancedOpen: (v: boolean) => void;
  updateStage: (s: Stage, patch: Partial<StageConfig>) => void;
  updateFallback: (s: Stage, patch: Partial<FallbackConfig> | null) => void;
}) {
  const meta = STAGE_META[stage];
  const fallback = config.fallback;

  return (
    <section className="rounded-lg border border-stone-200 dark:border-stone-800 p-5">
      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-lg">{meta.emoji}</span>
        <h2 className="text-lg font-semibold">{meta.zh}</h2>
        <span className="text-sm text-stone-500 dark:text-stone-400">· {meta.en}</span>
      </div>
      <p className="text-sm text-stone-600 dark:text-stone-400 mb-4">{meta.desc}</p>

      <div className="space-y-3">
        <ProviderModelRow
          label="主要 · Primary"
          provider={config.provider}
          model={config.model}
          modelsFor={modelsFor}
          envStatus={envStatus}
          onProviderChange={(p) => updateStage(stage, { provider: p })}
          onModelChange={(m) => updateStage(stage, { model: m })}
        />

        <details
          open={advancedOpen}
          onToggle={(e) => setAdvancedOpen((e.target as HTMLDetailsElement).open)}
          className="text-xs"
        >
          <summary className="cursor-pointer text-stone-500 dark:text-stone-400 hover:text-stone-700 dark:hover:text-stone-200">
            進階設定（temperature / max_tokens）
          </summary>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <label className="block">
              <div className="text-stone-500 dark:text-stone-400 mb-1">
                Temperature ({config.temperature})
              </div>
              <input
                type="range"
                min={0}
                max={1.5}
                step={0.05}
                value={config.temperature}
                onChange={(e) =>
                  updateStage(stage, { temperature: Number(e.target.value) })
                }
                className="w-full"
              />
            </label>
            <label className="block">
              <div className="text-stone-500 dark:text-stone-400 mb-1">Max tokens</div>
              <input
                type="number"
                min={100}
                max={16000}
                step={100}
                value={config.max_tokens}
                onChange={(e) =>
                  updateStage(stage, { max_tokens: Number(e.target.value) })
                }
                className="w-full px-2 py-1 rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-950"
              />
            </label>
          </div>
        </details>

        <div className="border-t border-stone-100 dark:border-stone-900 pt-3">
          <label className="flex items-center gap-2 text-sm text-stone-700 dark:text-stone-300 cursor-pointer">
            <input
              type="checkbox"
              checked={!!fallback}
              onChange={(e) =>
                e.target.checked
                  ? updateFallback(stage, { provider: "gemini", model: "gemini-2.5-flash" })
                  : updateFallback(stage, null)
              }
            />
            啟用備援 · Fallback
            <span className="text-xs text-stone-500 dark:text-stone-400">
              （主要 provider 失敗時自動切換）
            </span>
          </label>
          {fallback && (
            <div className="mt-3">
              <ProviderModelRow
                label=""
                provider={fallback.provider}
                model={fallback.model}
                modelsFor={modelsFor}
                envStatus={envStatus}
                onProviderChange={(p) => updateFallback(stage, { provider: p })}
                onModelChange={(m) => updateFallback(stage, { model: m })}
              />
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ProviderModelRow({
  label,
  provider,
  model,
  modelsFor,
  envStatus,
  onProviderChange,
  onModelChange,
}: {
  label: string;
  provider: Provider;
  model: string;
  modelsFor: (p: Provider) => string[];
  envStatus: EnvStatus;
  onProviderChange: (p: Provider) => void;
  onModelChange: (m: string) => void;
}) {
  const models = modelsFor(provider);
  const hasKey = envStatus[provider];
  const needsKey = provider !== "ollama";
  const showWarning = needsKey && !hasKey;
  const modelInList = models.includes(model);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3 items-end">
      <label className="block">
        {label && (
          <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">{label}</div>
        )}
        <select
          value={provider}
          onChange={(e) => onProviderChange(e.target.value as Provider)}
          className="w-full px-3 py-2 rounded-md border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-950 text-sm"
        >
          {PROVIDERS.map((p) => (
            <option key={p} value={p}>
              {PROVIDER_LABELS[p]}
            </option>
          ))}
        </select>
        {showWarning && (
          <p className="mt-1 text-xs text-amber-600 dark:text-amber-400">
            ⚠️ 需要在 <code>.env</code> 設定 {provider.toUpperCase()}_API_KEY，否則用到時會失敗
          </p>
        )}
      </label>

      <label className="block">
        <div className="text-xs text-stone-500 dark:text-stone-400 mb-1">Model</div>
        <select
          value={model}
          onChange={(e) => onModelChange(e.target.value)}
          className="w-full px-3 py-2 rounded-md border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-950 text-sm font-mono"
        >
          {!modelInList && (
            <option value={model}>{model}（自訂）</option>
          )}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
