#!/usr/bin/env node
/* Evaluate SmNav from sharp-money/index.html and print its section structure.
   Usage: node tests/smnav_parse.mjs path/to/index.html */
import { readFileSync } from 'fs';

const html = readFileSync(process.argv[2] || 'sharp-money/index.html', 'utf8');
const start = html.indexOf('SmNav=');
if (start < 0) { console.error('SmNav not found'); process.exit(2); }
let i = html.indexOf('[', start), depth = 0, end = -1;
for (let k = i; k < html.length; k++) {
  const c = html[k];
  if (c === '[') depth++;
  else if (c === ']') { depth--; if (depth === 0) { end = k; break; } }
}
if (end < 0) { console.error('SmNav unclosed'); process.exit(2); }
const U = { Fragment: 'Fragment', createElement: function () { return 'el'; } };
const SmNav = eval(html.slice(i, end + 1));
const sections = SmNav.map(e => e[0]);
const system = SmNav.find(e => e[0] === 'System');
const items = system && Array.isArray(system[1]) ? system[1].map(x => x[0]) : [];
const arities = Object.fromEntries(SmNav.map(e => [e[0], e.length]));
console.log(JSON.stringify({ sections, items, arities }));
