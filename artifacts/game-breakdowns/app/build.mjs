// Bundles app.jsx (React + Halaska kit) into ONE self-contained ../index.html.
// build_data.py runs this after writing data.json; the scheduled refresh publishes index.html + data.json.
// Run `node app/build.mjs` after editing app.jsx. Never hand-edit index.html.
import { build } from 'esbuild';
import { writeFileSync, copyFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(DIR, '..', '..', '..', 'game-breakdowns', 'index.html');

const r = await build({
  entryPoints: [resolve(DIR, 'app.jsx')], bundle: true, minify: true, write: false,
  format: 'iife', target: 'es2020', jsx: 'automatic', loader: { '.jsx': 'jsx', '.txt': 'text' },
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'none', nodePaths: [resolve(DIR, 'node_modules')],
});
const js = r.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const html = `<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Vault Game Breakdowns</title>
<style>html,body{margin:0;background:#1a1a1a;color-scheme:dark}body{-webkit-font-smoothing:antialiased}*{box-sizing:border-box}</style>
<div id="root"></div>
<script>${js}</script>
`;
writeFileSync(OUT, html);
console.log('index.html', (html.length / 1024).toFixed(0) + 'KB');
