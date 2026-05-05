export const prerender = false;

import type { APIRoute } from "astro";

/** Ask the local Ollama server which models are installed. */
export const GET: APIRoute = async () => {
  const host = process.env.OLLAMA_HOST || "http://localhost:11434";
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), 5000);
    const resp = await fetch(`${host}/api/tags`, { signal: ctrl.signal });
    clearTimeout(timer);
    if (!resp.ok) throw new Error(`Ollama returned HTTP ${resp.status}`);
    const data = (await resp.json()) as { models?: Array<{ name: string }> };
    const models = (data.models || [])
      .map((m) => m.name)
      .sort((a, b) => a.localeCompare(b));
    return new Response(
      JSON.stringify({ ok: true, models, host }),
      { headers: { "Content-Type": "application/json" } }
    );
  } catch (err) {
    return new Response(
      JSON.stringify({
        ok: false,
        error: String(err),
        models: [],
        host,
      }),
      { headers: { "Content-Type": "application/json" } }
    );
  }
};
