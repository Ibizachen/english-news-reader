// @ts-check
import { defineConfig } from 'astro/config';

import tailwindcss from '@tailwindcss/vite';
import react from '@astrojs/react';

// Static output mode: every page is prerendered to plain HTML, ready for
// any static host (Cloudflare Pages, Netlify, etc).
//
// For local development (`npm run dev`), admin/* and api/* still run
// because Vite serves all pages dynamically.
//
// For production (`bin/build_for_deploy.sh`), the build script temporarily
// moves admin/* and api/* out of src/pages/ so they're not in the deployed
// output — they're local-machine-only.
export default defineConfig({
  output: 'static',
  vite: {
    plugins: [tailwindcss()],
  },
  integrations: [react()],
});