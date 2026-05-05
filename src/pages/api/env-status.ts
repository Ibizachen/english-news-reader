export const prerender = false;

import fs from "node:fs";
import path from "node:path";
import type { APIRoute } from "astro";

/** Parse the project's .env file (non-strict; ignores comments and blank lines). */
function readDotEnv(): Record<string, string> {
  const envPath = path.join(process.cwd(), ".env");
  if (!fs.existsSync(envPath)) return {};
  const out: Record<string, string> = {};
  for (const raw of fs.readFileSync(envPath, "utf-8").split("\n")) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq === -1) continue;
    const key = line.slice(0, eq).trim();
    let value = line.slice(eq + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    out[key] = value;
  }
  return out;
}

/** Report which provider API keys are present in .env (and not just the placeholder). */
export const GET: APIRoute = async () => {
  const env = { ...process.env, ...readDotEnv() };
  const has = (key: string) => {
    const v = env[key];
    return Boolean(v && v.length > 5 && !v.startsWith("AIza你的") && !v.startsWith("sk-..."));
  };
  return new Response(
    JSON.stringify({
      ollama: true, // local; verified separately via /api/ollama-models
      gemini: has("GEMINI_API_KEY"),
      claude: has("ANTHROPIC_API_KEY"),
      openrouter: has("OPENROUTER_API_KEY"),
    }),
    { headers: { "Content-Type": "application/json" } }
  );
};
