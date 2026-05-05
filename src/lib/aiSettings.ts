import fs from "node:fs";
import path from "node:path";
import yaml from "js-yaml";

const PROJECT_ROOT = process.cwd();
const JSON_PATH = path.join(PROJECT_ROOT, "data", "config", "ai_settings.json");
const YAML_PATH = path.join(PROJECT_ROOT, "scripts", "ai_config.yaml");

export const PROVIDERS = ["ollama", "claude", "gemini", "openrouter"] as const;
export type Provider = (typeof PROVIDERS)[number];

export const STAGES = [
  "topic_selection",
  "article_synthesis",
  "translation",
  "key_terms_extraction",
  "quiz_generation",
] as const;
export type Stage = (typeof STAGES)[number];

export const STAGE_META: Record<Stage, { zh: string; en: string; desc: string }> = {
  topic_selection: {
    zh: "選題",
    en: "Topic Selection",
    desc: "從候選新聞挑出今天要寫的 4-5 個主題",
  },
  article_synthesis: {
    zh: "文章合成",
    en: "Article Synthesis",
    desc: "把 3-5 篇來源綜合成 600-1000 字英文新聞（最吃英文寫作品質）",
  },
  translation: {
    zh: "翻譯",
    en: "Translation",
    desc: "英文段落 → 繁體中文段落（段對段）",
  },
  key_terms_extraction: {
    zh: "易誤解詞彙",
    en: "Key Terms Extraction",
    desc: "從合成後的英文文章挑 3-5 個易誤讀詞（獨立階段，避免從原始來源誤引句子）",
  },
  quiz_generation: {
    zh: "出題",
    en: "Quiz Generation",
    desc: "4 題選擇題（detail / inference / vocabulary / main_idea）+ 中文解析",
  },
};

export interface FallbackConfig {
  provider: Provider;
  model: string;
}

export interface StageConfig {
  provider: Provider;
  model: string;
  temperature: number;
  max_tokens: number;
  fallback?: FallbackConfig;
}

export interface AiSettings {
  ai_pipeline: Record<Stage, StageConfig>;
  global: {
    json_retry_max: number;
    stage_failure_isolation: boolean;
    cost_cap_usd_per_run: number;
  };
}

/** Load default config from scripts/ai_config.yaml. */
function readDefaults(): AiSettings {
  const raw = fs.readFileSync(YAML_PATH, "utf-8");
  return yaml.load(raw) as AiSettings;
}

/** Returns the *effective* settings: JSON if user has saved one, else YAML defaults. */
export function readSettings(): AiSettings {
  if (fs.existsSync(JSON_PATH)) {
    try {
      return JSON.parse(fs.readFileSync(JSON_PATH, "utf-8"));
    } catch (err) {
      console.error(`Failed to parse ${JSON_PATH}, falling back to YAML defaults:`, err);
    }
  }
  return readDefaults();
}

/** Returns true if the user has not saved a custom JSON config. */
export function isUsingDefaults(): boolean {
  return !fs.existsSync(JSON_PATH);
}

/** Save settings to data/config/ai_settings.json. */
export function writeSettings(settings: AiSettings): void {
  fs.mkdirSync(path.dirname(JSON_PATH), { recursive: true });
  fs.writeFileSync(
    JSON_PATH,
    JSON.stringify(settings, null, 2) + "\n",
    "utf-8"
  );
}

/** Delete the JSON file so the pipeline reverts to YAML defaults. */
export function resetToDefaults(): void {
  if (fs.existsSync(JSON_PATH)) {
    fs.unlinkSync(JSON_PATH);
  }
}
