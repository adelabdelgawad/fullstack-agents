import { chromium } from "playwright-core";
import { execFileSync, spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { snapshot, stubSockets } from "./normalize.js";
import { ROOTS, SEED, STATES } from "./states.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const VOLATILE = new Set(["t", "since", "_"]);
const LIVE_PATHS = new Set(["/api/herdr", "/api/herdr/screen"]);
const STREAMS = new Set(["/api/herdr/live", "/api/herdr/client"]);

function parseArgs(argv) {
  const out = {_: []};
  for (let i = 0; i < argv.length; i++) {
    if (argv[i].startsWith("--")) out[argv[i].slice(2)] = argv[++i];
    else out._.push(argv[i]);
  }
  return out;
}

const args = parseArgs(process.argv.slice(2));
const opt = {
  mode: args._[0] || "compare",
  base: args.base || process.env.PARITY_BASE || "http://127.0.0.1:18766",
  live: args.live || process.env.PARITY_LIVE || "http://127.0.0.1:8766",
  fixtures: args.fixtures || process.env.PARITY_FIXTURES,
  left: args.left || "/",
  right: args.right || "/next",
  chrome: process.env.PARITY_CHROME || `${os.homedir()}/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`,
};
if (!opt.fixtures) throw new Error("set --fixtures DIR or PARITY_FIXTURES (keep it outside the repository)");
opt.out = args.out || process.env.PARITY_OUT || path.join(opt.fixtures, "out");
const units = args.unit ? new Set(args.unit.split(",")) : null;
const names = args.state ? new Set(args.state.split(",")) : null;
const states = STATES.filter(s => (!units || units.has(s.unit)) && (!names || names.has(s.name)));
const common = execFileSync("git", ["rev-parse", "--path-format=absolute", "--git-common-dir"], {cwd: HERE}).toString().trim();
const token = fs.readFileSync(path.join(common, "fsa-team", "dashboard.token"), "utf8").trim();
const liveToken = process.env.PARITY_LIVE_TOKEN || token;
const fixtureFile = path.join(opt.fixtures, "fixtures.json");

function apiKey(method, raw) {
  const url = new URL(raw);
  const q = [...url.searchParams].filter(([k]) => !VOLATILE.has(k)).sort((a, b) => (a[0] + a[1] < b[0] + b[1] ? -1 : 1));
  return `${method} ${url.pathname}${q.length ? `?${new URLSearchParams(q)}` : ""}`;
}

async function openPage(browser, state, onApi, fixedTime) {
  const ctx = await browser.newContext({locale: "en-GB", timezoneId: "UTC", viewport: {width: 1440, height: 900}});
  await ctx.addInitScript(seed => {
    try { localStorage.clear(); for (const [k, v] of Object.entries(seed)) localStorage.setItem(k, v); } catch (e) {}
  }, {...SEED, ...state.seed});
  await ctx.addInitScript(stubSockets);
  const page = await ctx.newPage();
  if (fixedTime) await page.clock.setFixedTime(fixedTime);
  const activity = {last: Date.now()};
  await page.route("**/api/**", route => { activity.last = Date.now(); return onApi(route); });
  return {ctx, page, activity};
}

async function settle(page, activity) {
  await page.waitForTimeout(400);
  const end = Date.now() + 5000;
  while (Date.now() - activity.last < 300 && Date.now() < end) await page.waitForTimeout(100);
  await page.waitForTimeout(200);
}

async function runSteps(page, activity, steps, errors) {
  for (const step of steps || []) {
    try {
      if (step.click) await page.click(step.click, {timeout: 3000});
      else if (step.rightclick) await page.click(step.rightclick, {button: "right", timeout: 3000});
      else if (step.fill) await page.fill(step.fill, step.value, {timeout: 3000});
      else if (step.select) await page.selectOption(step.select, step.value, {timeout: 3000});
      else if (step.key) await page.keyboard.press(step.key);
    } catch (e) {
      errors.push(`step ${JSON.stringify(step)}: ${e.message.split("\n")[0]}`);
      return;
    }
    await settle(page, activity);
  }
}

async function record(browser) {
  const store = {recordedAt: Date.now(), entries: {}};
  for (const state of states) {
    const errors = [];
    const {ctx, page, activity} = await openPage(browser, state, async route => {
      const req = route.request();
      const url = new URL(req.url());
      if (req.method() !== "GET") return route.fulfill({status: 200, contentType: "application/json", body: "{}"});
      if (STREAMS.has(url.pathname)) return route.abort();
      const target = LIVE_PATHS.has(url.pathname) ? `${opt.live}${url.pathname}${url.search || "?"}&t=${liveToken}` : req.url();
      const resp = await route.fetch({url: target});
      const body = await resp.text();
      store.entries[apiKey("GET", req.url())] ??= {status: resp.status(), contentType: resp.headers()["content-type"] || "", body};
      return route.fulfill({status: resp.status(), contentType: resp.headers()["content-type"], body});
    });
    await page.goto(`${opt.base}${opt.left}?t=${token}`);
    await settle(page, activity);
    await runSteps(page, activity, state.steps, errors);
    console.log(`recorded ${state.name}${errors.length ? ` (${errors.join("; ")})` : ""}`);
    await page.unrouteAll({behavior: "ignoreErrors"});
    await ctx.close();
  }
  fs.mkdirSync(opt.fixtures, {recursive: true});
  fs.writeFileSync(fixtureFile, JSON.stringify(store));
  console.log(`${Object.keys(store.entries).length} responses -> ${fixtureFile}`);
}

async function capture(browser, fx, state, pagePath) {
  const errors = [];
  const {ctx, page, activity} = await openPage(browser, state, route => {
    const req = route.request();
    const hit = req.method() === "GET" ? fx.entries[apiKey("GET", req.url())] : {status: 200, contentType: "application/json", body: "{}"};
    if (!hit) {
      errors.push(`no fixture: ${apiKey(req.method(), req.url())}`);
      return route.fulfill({status: 404, contentType: "text/plain", body: "no fixture"});
    }
    return route.fulfill({status: hit.status, contentType: hit.contentType, body: hit.body});
  }, fx.recordedAt);
  page.on("pageerror", e => errors.push(`pageerror: ${e.message}`));
  await page.goto(`${opt.base}${pagePath}?t=${token}`);
  await settle(page, activity);
  await runSteps(page, activity, state.steps, errors);
  const snap = await page.evaluate(snapshot, state.roots || ROOTS);
  await page.unrouteAll({behavior: "ignoreErrors"});
  await ctx.close();
  return {snap, errors};
}

function writeDiff(dir, root, a, b) {
  const stem = root.replace(/[^a-z0-9]+/gi, "_");
  const left = path.join(dir, `${stem}.left.txt`);
  const right = path.join(dir, `${stem}.right.txt`);
  fs.writeFileSync(left, `${a ?? "(missing)"}\n`);
  fs.writeFileSync(right, `${b ?? "(missing)"}\n`);
  const diff = spawnSync("diff", ["-u", left, right]).stdout.toString();
  fs.writeFileSync(path.join(dir, `${stem}.diff`), diff);
  return diff.split("\n").filter(l => /^[-+][^-+]/.test(l)).length;
}

async function compare(browser) {
  const fx = JSON.parse(fs.readFileSync(fixtureFile, "utf8"));
  fs.rmSync(opt.out, {recursive: true, force: true});
  const rows = [];
  for (const state of states) {
    const a = await capture(browser, fx, state, opt.left);
    const b = await capture(browser, fx, state, opt.right);
    const dir = path.join(opt.out, state.name);
    fs.mkdirSync(dir, {recursive: true});
    for (const root of Object.keys(a.snap)) {
      const same = a.snap[root] === b.snap[root];
      const lines = same ? 0 : writeDiff(dir, root, a.snap[root], b.snap[root]);
      rows.push({state: state.name, unit: state.unit, root, result: same ? "equal" : `DIFF ${lines} lines`});
    }
    const errors = [...a.errors.map(e => `left ${e}`), ...b.errors.map(e => `right ${e}`)];
    if (errors.length) rows.push({state: state.name, unit: state.unit, root: "(harness)", result: `ERROR ${errors.join(" | ")}`});
  }
  fs.writeFileSync(path.join(opt.out, "report.json"), JSON.stringify(rows, null, 1));
  for (const r of rows) console.log(`${r.unit}\t${r.state}\t${r.root}\t${r.result}`);
  const bad = rows.filter(r => r.result !== "equal").length;
  console.log(`${bad ? "RED" : "GREEN"}: ${rows.length - bad}/${rows.length} equal; diffs in ${opt.out}`);
  return bad ? 1 : 0;
}

const browser = await chromium.launch({executablePath: opt.chrome});
let code = 0;
try {
  if (opt.mode === "record") await record(browser);
  else code = await compare(browser);
} finally {
  await browser.close();
}
process.exit(code);
