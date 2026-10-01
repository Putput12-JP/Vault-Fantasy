// Bundles app.jsx (React + Halaska kit + team data) into ONE self-contained
// ../halaska-nba.html, like the other nba/mocks files. Run: node build.mjs
import { build } from 'esbuild';
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const OUT = resolve(DIR, '..', '..', 'halaska-nba.html');
const r = await build({
  entryPoints: [resolve(DIR, 'app.jsx')], bundle: true, minify: true, write: false,
  format: 'iife', target: 'es2020', jsx: 'automatic', loader: { '.jsx': 'jsx', '.json': 'json' },
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'none', nodePaths: [resolve(DIR, 'node_modules')],
});
const js = r.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
const html = `<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Vault NBA on Halaska</title>
<style>html,body{margin:0;background:#1a1a1a;color-scheme:dark}body{-webkit-font-smoothing:antialiased}*{box-sizing:border-box}</style>
<div id="root"></div>
<script>${js}</script>
`;
writeFileSync(OUT, html);
console.log('halaska-nba.html', (html.length / 1024).toFixed(0) + 'KB');
