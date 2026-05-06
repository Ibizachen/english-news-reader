// =============================================================================
// Cloudflare Worker — cron trigger for english-news-reader/daily.yml
// =============================================================================
//
// WHY: GitHub Actions' built-in `schedule:` trigger is unreliable, especially
// for newly-created workflows. After 24+ hours and 4 schedule changes, the
// workflow had never fired automatically. Cloudflare Workers Cron Triggers
// are far more reliable — they fire to within ~1 minute of scheduled time
// every time.
//
// WHAT IT DOES: On a schedule (configured in Cloudflare dashboard), this
// Worker POSTs to GitHub's REST API to manually dispatch the daily.yml
// workflow. Effectively the same as clicking "Run workflow" in the GitHub
// UI, just automated.
//
// CONFIGURATION (set in Cloudflare dashboard, NOT in code):
//   Cron Trigger:  "13 22 * * *"      → Taipei 06:13 daily
//   Secret:        GITHUB_TOKEN       → GitHub PAT with `workflow` scope
//
// SETUP STEPS: see ./README.md
// =============================================================================

const OWNER = "Ibizachen";
const REPO = "english-news-reader";
const WORKFLOW = "daily.yml";

/**
 * Trigger the GitHub Actions workflow.
 * Returns { ok, status, body } describing the API response.
 */
async function triggerWorkflow(token) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${WORKFLOW}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      // GitHub accepts `Bearer <token>` for fine-grained or classic PATs.
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      // Required by GitHub API (returns 403 without it).
      "User-Agent": "english-news-reader-cron-trigger",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  // 204 No Content = success. Body is empty on success, so only read text on failure.
  return {
    ok: response.ok,
    status: response.status,
    body: response.ok ? "" : await response.text(),
  };
}

export default {
  /**
   * Fires on the configured Cron Trigger.
   * If the trigger fails (network error, bad token, GitHub down, etc.) we
   * throw — Cloudflare logs the error and shows it in the Worker dashboard.
   */
  async scheduled(event, env, ctx) {
    console.log(`[cron] firing at ${new Date().toISOString()}`);
    const result = await triggerWorkflow(env.GITHUB_TOKEN);
    if (!result.ok) {
      console.error(`[cron] GitHub API failed: ${result.status} ${result.body}`);
      throw new Error(`GitHub API ${result.status}: ${result.body}`);
    }
    console.log("[cron] ✓ workflow dispatched successfully");
  },

  /**
   * HTTP handler — only used as a "is the worker alive?" status page.
   * No write actions allowed via HTTP (we don't want a public URL that
   * triggers our pipeline). Manual testing should use the dashboard's
   * "Trigger Cron" button.
   */
  async fetch(request, env) {
    return new Response(
      [
        "english-news-reader cron trigger",
        "",
        "This Worker fires on a Cloudflare Cron Trigger and POSTs to",
        "GitHub Actions to start the daily article generation workflow.",
        "",
        "Manual test: use the 'Trigger Cron' button in the Cloudflare",
        "Worker dashboard (Settings → Triggers → Cron Triggers).",
        "",
      ].join("\n"),
      { headers: { "Content-Type": "text/plain; charset=utf-8" } },
    );
  },
};
