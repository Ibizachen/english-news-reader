export const prerender = false;

import type { APIRoute } from "astro";
import {
  readSettings,
  writeSettings,
  resetToDefaults,
  isUsingDefaults,
} from "../../lib/aiSettings";

export const GET: APIRoute = async () => {
  return new Response(
    JSON.stringify({
      settings: readSettings(),
      usingDefaults: isUsingDefaults(),
    }),
    { headers: { "Content-Type": "application/json" } }
  );
};

export const POST: APIRoute = async ({ request }) => {
  try {
    const body = await request.json();
    if (!body || !body.ai_pipeline) {
      return new Response(
        JSON.stringify({ ok: false, error: "Missing ai_pipeline in body" }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }
    writeSettings(body);
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      { status: 400, headers: { "Content-Type": "application/json" } }
    );
  }
};

export const DELETE: APIRoute = async () => {
  try {
    resetToDefaults();
    return new Response(JSON.stringify({ ok: true }), {
      headers: { "Content-Type": "application/json" },
    });
  } catch (err) {
    return new Response(
      JSON.stringify({ ok: false, error: String(err) }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
};
