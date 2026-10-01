// Bundles entry.jsx (React + Halaska kit + the NBA views) into dist.js, which
// scripts/render_app.py inlines into projections.html. dist.js is committed so the daily
// GitHub Actions refresh needs no npm. Rebuild after editing views.jsx:  node build.mjs
import { build } from 'esbuild';
import { writeFileSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = dirname(fileURLToPath(import.meta.url));
const r = await build({
  entryPoints: [resolve(DIR, 'entry.jsx')], bundle: true, minify: true, write: false,
  format: 'iife', target: 'es2020', jsx: 'automatic', loader: { '.jsx': 'jsx' },
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'none', nodePaths: [resolve(DIR, 'node_modules')],
});
const js = r.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
writeFileSync(resolve(DIR, 'dist.js'), js);
console.log('dist.js', (js.length / 1024).toFixed(0) + 'KB');
