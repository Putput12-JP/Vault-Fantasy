// Extracts evLn from sharp-money/index.html and prints its output for tests/evln_cases.json.
// Usage: node tests/test_ev_line_key.js [--dump]   (exit non-zero when it disagrees with tests/evln_expected.json)
const fs = require("fs"), path = require("path");
const html = fs.readFileSync(path.join(__dirname, "..", "sharp-money", "index.html"), "utf8");
const m = html.match(/function evLn\(x\)\{.*?\}(?=function evKey)/);
if (!m) { console.error("evLn not found"); process.exit(2); }
const evLn = new Function(m[0] + ";return evLn")();
// -0 is not valid JSON, so the case file carries -0.0 which JSON.parse turns into -0.
const cases = JSON.parse(fs.readFileSync(path.join(__dirname, "evln_cases.json"), "utf8"));
const out = cases.map(evLn);
if (process.argv.includes("--dump")) { console.log(JSON.stringify(out)); process.exit(0); }
const exp = JSON.parse(fs.readFileSync(path.join(__dirname, "evln_expected.json"), "utf8"));
let bad = 0;
cases.forEach((c, i) => { if (out[i] !== exp[i]) { bad++; console.log("MISMATCH", Object.is(c, -0) ? "-0" : JSON.stringify(c), JSON.stringify(out[i]), "!=", JSON.stringify(exp[i])); } });
console.log(bad ? bad + " mismatches" : "evLn matches expected on " + cases.length + " cases");
process.exit(bad ? 1 : 0);
