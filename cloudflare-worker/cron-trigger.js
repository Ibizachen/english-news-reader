// =============================================================================
// Cloudflare Worker — cron triggers for english-news-reader
// =============================================================================
//
// WHY: GitHub Actions' built-in `schedule:` trigger is unreliable for this
// repo. Cloudflare Workers Cron Triggers fire reliably within ~1 minute.
//
// WORKFLOWS MANAGED:
//   daily.yml         → every day at Taipei 06:13   (UTC "13 22 * * *")
//   weekly_series.yml → every Monday at Taipei 09:00 (UTC "0 1 * * 1")
//
// CONFIGURATION (set in Cloudflare dashboard, NOT in code):
//   Cron Triggers (add both):
//     "13 22 * * *"   → daily articles
//     "0 1 * * 1"     → weekly Stories series
//   Secret:
//     GITHUB_TOKEN    → GitHub PAT with `workflow` scope
//
// SETUP STEPS: see ./README.md
// =============================================================================

const OWNER = "Ibizachen";
const REPO = "english-news-reader";

// Maps cron expression → GitHub Actions workflow filename.
const CRON_TO_WORKFLOW = {
  "13 22 * * *": "daily.yml",
  "0 1 * * 1":   "weekly_series.yml",
};

/**
 * Dispatch a GitHub Actions workflow.
 * Returns { ok, status, body } describing the API response.
 */
async function triggerWorkflow(token, workflow) {
  const url = `https://api.github.com/repos/${OWNER}/${REPO}/actions/workflows/${workflow}/dispatches`;
  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "english-news-reader-cron-trigger",
    },
    body: JSON.stringify({ ref: "main" }),
  });
  return {
    ok: response.ok,
    status: response.status,
    body: response.ok ? "" : await response.text(),
  };
}

export default {
  async scheduled(event, env, ctx) {
    const cron = event.cron;
    const workflow = CRON_TO_WORKFLOW[cron];

    if (!workflow) {
      console.error(`[cron] Unknown cron expression: "${cron}" — no workflow mapped`);
      throw new Error(`No workflow mapped for cron: ${cron}`);
    }

    console.log(`[cron] ${cron} → ${workflow} at ${new Date().toISOString()}`);
    const result = await triggerWorkflow(env.GITHUB_TOKEN, workflow);

    if (!result.ok) {
      console.error(`[cron] GitHub API failed: ${result.status} ${result.body}`);
      throw new Error(`GitHub API ${result.status}: ${result.body}`);
    }
    console.log(`[cron] ✓ ${workflow} dispatched successfully`);
  },

  async fetch(request, env) {
    return new Response(
      [
        "english-news-reader cron trigger",
        "",
        "Cron schedules (UTC):",
        "  13 22 * * *  → daily.yml          (Taipei 06:13 daily)",
        "  0 1 * * 1    → weekly_series.yml  (Taipei 09:00 Monday)",
        "",
        "Manual test: use the 'Trigger Cron' button in the Cloudflare",
        "Worker dashboard (Settings → Triggers → Cron Triggers).",
        "",
      ].join("\n"),
      { headers: { "Content-Type": "text/plain; charset=utf-8" } },
    );
  },
};
