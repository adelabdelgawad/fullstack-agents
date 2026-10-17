// Fleet overview: summary tiles, usage strip, worker squares, activity feed, filters, history, wall mode and theme.
const fleetStore = {
  get(k, d) { try { const v = localStorage.getItem("fsa-" + k); return v === null ? d : v; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem("fsa-" + k, v); } catch (e) {} },
};
const fleet = {
  filter: fleetStore.get("filter", "all"), sort: fleetStore.get("sort", "stage"), text: "",
  feed: fleetStore.get("feed", "1") === "1", theme: fleetStore.get("theme", "system"), tpm: [],
};
const FILTERS = [["all", "All"], ["running", "Running"], ["waiting", "Waiting"], ["stale", "Stale"], ["blowouts", "Blowouts"]];
const SORTS = [["stage", "Stage order"], ["updated", "Last update"], ["cost", "Cost"], ["context", "Context fill"]];
const MODELS = [["opus", "Opus"], ["sonnet", "Sonnet"], ["haiku", "Haiku"], ["fable", "Fable"], ["gpt", "Codex"], ["grok", "Grok"]];

function applyTheme(theme) {
  fleet.theme = theme;
  fleetStore.set("theme", theme);
  if (theme === "system") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = theme;
  syncNav();
}

function syncNav() {
  const set = (el, on) => el && el.setAttribute("aria-pressed", String(on));
  document.querySelectorAll("[data-ftheme]").forEach(b => set(b, b.dataset.ftheme === fleet.theme));
  set(document.getElementById("ffeed"), fleet.feed);
  const wall = document.getElementById("fwall");
  if (wall) wall.setAttribute("aria-checked", String(document.documentElement.classList.contains("wall")));
  const feed = document.getElementById("ffeed");
  if (feed) feed.hidden = typeof view !== "undefined" && view !== "agents";
}

document.addEventListener("click", e => {
  const t = e.target.closest && e.target.closest("header [data-ftheme], #ffeed, #fwall");
  if (!t) return;
  if (t.dataset.ftheme) applyTheme(t.dataset.ftheme);
  else if (t.id === "ffeed") { fleet.feed = !fleet.feed; fleetStore.set("feed", fleet.feed ? "1" : "0"); syncNav(); render(); }
  else setWall(!document.documentElement.classList.contains("wall"));
});
applyTheme(fleet.theme);
if (fleetStore.get("wall", "0") === "1") document.documentElement.classList.add("wall");

const fmtTokens = n => !n ? "0" : n >= 1e9 ? (n / 1e9).toFixed(2) + "B" : n >= 1e6 ? (n / 1e6).toFixed(n >= 1e8 ? 0 : 1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "k" : String(n);
const fmtCost = c => c === null || c === undefined ? "—" : c >= 100 ? "$" + Math.round(c) : "$" + c.toFixed(2);
const modelFamily = m => { const x = String(m || "").toLowerCase(); return (MODELS.find(([k]) => x.includes(k)) || [x.includes("codex") ? "gpt" : "other"])[0]; };
const modelShort = m => String(m || "").replace(/^claude-/, "").replace(/-(\d+)-(\d+)$/, " $1.$2").replace(/-(\d+)$/, " $1");
const isStale = c => (c.sessions || []).some(s => s.state === "quiet");
const isRunning = c => c.sessions.some(s => s.state === "working") || c.runs.some(r => r.state === "running");

function fleetMatches(c) {
  const f = fleet.filter, u = c.usage;
  if (f === "running" && !isRunning(c)) return false;
  if (f === "waiting" && !needsHuman(c)) return false;
  if (f === "stale" && !isStale(c)) return false;
  if (f === "blowouts" && !(u && u.blowout)) return false;
  if (!fleet.text) return true;
  const hay = [c.title, c.label, c.tree && c.tree.branch, u && u.model, ...c.sessions.map(s => s.name + " " + (s.branch || ""))].join(" ").toLowerCase();
  return hay.includes(fleet.text.toLowerCase());
}

function fleetCompare(a, b) {
  const x = a, y = b, ux = x.usage || {}, uy = y.usage || {};
  if (fleet.sort === "updated") return y.updated - x.updated;
  if (fleet.sort === "cost") return (uy.cost || 0) - (ux.cost || 0) || y.updated - x.updated;
  if (fleet.sort === "context") return (uy.fill || 0) - (ux.fill || 0) || y.updated - x.updated;
  return rank(x) - rank(y) || y.updated - x.updated;
}

function sparkline(points) {
  if (points.length < 2) return "";
  const max = Math.max(...points, 1), step = 100 / (points.length - 1);
  return `<svg viewBox="0 0 100 22" preserveAspectRatio="none" aria-hidden="true"><polyline points="${points.map((p, i) => `${(i * step).toFixed(1)},${(21 - p / max * 19).toFixed(1)}`).join(" ")}"/></svg>`;
}

function noteTpm() {
  const t = state && state.totals;
  if (!t) return;
  fleet.tpm.push(t.tpm || 0);
  if (fleet.tpm.length > 60) fleet.tpm.shift();
}

function fleetTiles() {
  const t = (state && state.totals) || {};
  const tile = (label, value, sub, cls = "", extra = "") => `<div class="ft ${cls}"><div class="ft-l">${esc(label)}</div><div class="ft-v">${esc(value)}</div>${sub ? `<div class="ft-s">${esc(sub)}</div>` : ""}${extra}</div>`;
  return `<section class="fleet-tiles" aria-label="Fleet summary">
    ${tile("Sessions active (1 h)", t.live ?? 0, `${t.working || 0} working · ${t.waiting || 0} waiting · ${t.stale || 0} stale`)}
    ${tile("Waiting on you", t.waiting ?? 0, "approve, answer or decide", t.waiting ? "warn" : "")}
    ${tile("Workers running", t.workers ?? 0, t.failed ? `${t.failed} failed run${t.failed === 1 ? "" : "s"}` : "subagents and implementer runs", t.failed ? "bad" : "")}
    ${tile("Context blowouts", t.blowouts ?? 0, "compacted or ≥ 90% full", t.blowouts ? "bad" : "")}
    ${planTile("Claude plan", ((state && state.plan) || {}).claude)}
    ${planTile("Codex plan", ((state && state.plan) || {}).codex)}
    ${spendTile("Grok", ((state && state.plan) || {}).grok)}
    ${tile("Tokens, last minute", fmtTokens(t.tpm), `${fmtTokens(t.tokens_today)} today · ${fmtCost(t.cost_today)} API-equivalent`, "", sparkline(fleet.tpm))}
  </section>`;
}

const untilText = iso => { const s = (Date.parse(iso) - Date.now()) / 1000; return !(s > 0) ? "" : s < 3600 ? `${Math.round(s / 60)}m` : s < 172800 ? `${Math.floor(s / 3600)}h ${Math.round(s % 3600 / 60)}m` : `${Math.round(s / 86400)}d`; };

function planTile(label, p) {
  if (!p || !p.windows) return `<div class="ft"><div class="ft-l">${esc(label)}</div><div class="ft-v">—</div><div class="ft-s">${esc((p && p.error) || "no data")}</div></div>`;
  const worst = Math.max(0, ...p.windows.map(w => w.pct ?? 0)), cls = worst >= 90 ? "bad" : worst >= 75 ? "warn" : "";
  const row = w => { const known = w.pct !== null && w.pct !== undefined, tone = !known ? "ok" : w.pct >= 90 ? "bad" : w.pct >= 75 ? "warn" : "ok", until = untilText(w.resets_at);
    const tip = known ? `${label} ${w.name}: ${w.pct}% used${until ? `, resets in ${until}` : ""}` : `${label} ${w.name}: window reset since the last reading`;
    return `<div class="plan-row" title="${esc(tip)}"><span>${esc(w.name)}</span><span class="orc-bar ctx-${tone}"><span style="width:${known ? Math.min(w.pct, 100) : 0}%"></span></span><b>${known ? Math.round(w.pct) + "%" : "—"}</b><em>${until ? "↻ " + esc(until) : known ? "" : "reset"}</em></div>`; };
  return `<div class="ft plan ${cls}"${p.stale ? ` title="${esc(p.stale)}"` : ""}><div class="ft-l">${esc(label)}${p.plan ? ` · ${esc(p.plan)}` : ""}${p.stale ? ' <span class="stale">· stale</span>' : ""}</div>${p.windows.map(row).join("")}${creditsLine(p)}</div>`;
}

function spendTile(label, p) {
  if (!p || !p.spend) return `<div class="ft"><div class="ft-l">${esc(label)}</div><div class="ft-v">—</div><div class="ft-s">${esc((p && p.error) || "no data")}</div></div>`;
  const row = x => `<div class="plan-row spend"><span>${esc(x.name)}</span><b>${esc(fmtTokens(x.tokens))}</b><em>${esc(fmtCost(x.cost))}</em></div>`;
  return `<div class="ft plan" title="xAI reports no plan limits to opencode; cost is opencode's API-equivalent estimate"><div class="ft-l">${esc(label)} · ${esc(p.plan)}</div>${p.spend.map(row).join("")}<div class="plan-credits">last used ${esc(ago(p.last_at))} ago · no plan limits reported</div></div>`;
}

function creditsLine(p) {
  if (!p.credits) return "";
  const capped = p.windows.some(w => (w.pct ?? 0) >= 100);
  const bal = p.credits.unlimited ? "unlimited" : Math.round(p.credits.balance).toLocaleString();
  return `<div class="plan-credits${capped ? " on" : ""}" title="${esc(capped ? "A plan window is used up; runs are paid from credits" : "Credit balance available after the plan limits")}">${capped ? "on credits · " : "credits · "}${esc(bal)} left</div>`;
}

function fleetToolbar(shown, total) {
  const seg = (items, cur, attr) => `<div class="fseg" role="group">${items.map(([k, label]) => `<button ${attr}="${k}" aria-pressed="${cur === k}">${label}</button>`).join("")}</div>`;
  return `<div class="fleet-toolbar">
    ${seg(FILTERS, fleet.filter, "data-ffilter")}
    <label>Sort <select id="fsort">${SORTS.map(([k, l]) => `<option value="${k}" ${fleet.sort === k ? "selected" : ""}>${l}</option>`).join("")}</select></label>
    <input id="ftext" type="search" placeholder="Filter by name, branch or model" value="${esc(fleet.text)}" aria-label="Filter cards">
    <span class="fcount">${shown === total ? `${total} orchestrators` : `${shown} of ${total} shown`}</span>
  </div>`;
}


function squaresHtml(c) {
  const runs = (c.runs || []).map(r => ({kind: "run", id: r.id, state: r.state, model: r.model || r.engine, label: `${r.mode} ${r.unit || r.id}`, cause: r.cause}));
  const agents = cardAgents(c).filter(a => !a.shell).map(a => ({kind: "agent", id: a.id, sid: a.sid, state: a.state, model: a.model, label: a.label}));
  const all = [...runs, ...agents];
  if (!all.length) return "";
  const cls = s => s === "running" ? "running" : ["failed", "abandoned"].includes(s) ? "failed" : s === "stalled" ? "stalled" : "done";
  const sq = x => `<button class="sq m-${modelFamily(x.model)} ${cls(x.state)}" ${x.kind === "run" ? `data-run-log="${esc(x.id)}" data-run-card="${esc(c.key)}"` : `data-asid="${esc(x.sid)}" data-agent="${esc(x.id)}"`} title="${esc(`${x.label} — ${x.state}${x.model ? " · " + modelShort(x.model) : ""}${x.cause ? "\n" + x.cause : ""}`)}" aria-label="${esc(`${x.label}, ${x.state}`)}"></button>`;
  return `<div class="squares" role="group" aria-label="Workers">${all.slice(-60).map(sq).join("")}</div>`;
}

function feedHtml() {
  if (!fleet.feed) return "";
  const items = (state && state.activity) || [];
  const t = at => new Date(at * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"});
  const known = new Set(((state && state.cards) || []).map(c => c.key));
  const rows = items.map(e => `<li class="${esc(e.tone)}"${e.key && known.has(e.key) ? ` data-open="${esc(e.key)}" tabindex="0"` : ""}><time>${t(e.at)}</time><div class="fbody" title="${esc(e.text)}"><b>${esc(e.who)}</b> <span class="ftext">${esc(e.text)}</span></div></li>`).join("");
  return `<section class="feed" aria-label="Activity"><h2>Activity <span>newest first</span></h2>${rows ? `<ol>${rows}</ol>` : '<div class="fnone">No activity since the dashboard started.</div>'}<div class="fcount" style="margin-top:8px">Only the latest 150 events are kept in memory.</div></section>`;
}

function legendHtml() {
  return `<div class="legend" aria-label="Legend"><span>Square colour is the model:</span>${MODELS.map(([k, l]) => `<span><span class="sq m-${k}"></span>${l}</span>`).join("")}<span><span class="sq m-other running"></span>running</span><span><span class="sq m-other done"></span>done</span><span><span class="sq failed"></span>failed</span><span>Context bar: green &lt; 80%, amber &lt; 90%, red above · N× = compactions</span></div>`;
}

function workersSection(c) {
  const runs = (c.runs || []).map(r => ({name: `${r.mode} ${r.unit || r.id}`, kind: "implementer run", u: {model: r.model || r.engine}, state: r.state, at: r.started, cause: r.cause}));
  const rows = (c.sessions || []).flatMap(s => [
    {name: s.name, kind: "orchestrator", u: s.usage || {model: s.model}, state: s.state, lead: true},
    ...Object.entries((s.usage && s.usage.agents) || {}).map(([id, a]) => {
      const live = cardAgents(c).find(x => x.id === id) || {};
      return {name: live.label || a.label || id, kind: "subagent", u: a, state: live.state || "completed", at: live.at};
    }),
  ]).concat(runs);
  if (!rows.length) return "";
  const num = (v, f) => v === undefined || v === null ? "—" : f(v);
  const tr = r => `<tr class="${["failed", "abandoned"].includes(r.state) ? "bad" : ""}"><td>${r.lead ? "<b>" + esc(r.name) + "</b>" : esc(r.name)}<div class="s">${esc(r.kind)}${r.cause ? " · " + esc(r.cause) : ""}</div></td><td><span class="mchip m-${modelFamily(r.u.model)}">${esc(modelShort(r.u.model) || "?")}</span></td><td>${esc(STATE_TEXT[r.state] || r.state || "")}</td><td class="num">${r.u.fill !== undefined ? `${Math.round(r.u.fill * 100)}%<span class="orc-bar"><span style="width:${Math.round(r.u.fill * 100)}%"></span></span>` : "—"}</td><td class="num">${num(r.u.tokens, fmtTokens)}</td><td class="num">${fmtCost(r.u.cost)}</td><td class="num">${r.at ? ago(r.at) : ""}</td></tr>`;
  return infoSection(c, "workers", `Orchestrator and workers (${rows.length})`, `<table class="usage-table"><thead><tr><th>Agent</th><th>Model</th><th>State</th><th>Context</th><th>Tokens</th><th>Est. cost</th><th>Age</th></tr></thead><tbody>${rows.map(tr).join("")}</tbody></table><div class="s">Cost is an estimate from token counts and a price table, not a bill.</div>`, "", true);
}

function activitySection(c) {
  const items = ((state && state.activity) || []).filter(e => e.key === c.key).slice(0, 20);
  const t = at => new Date(at * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"});
  const body = items.length ? `<ol class="detail-feed">${items.map(e => `<li class="${esc(e.tone)}"><time>${t(e.at)}</time> ${esc(e.text)}</li>`).join("")}</ol>` : '<div class="s">No activity recorded since the dashboard started.</div>';
  return infoSection(c, "activity", "Recent activity", body, "", true);
}

function renderHistory() {
  const rows = ((state && state.history) || []).filter(h => !fleet.text || `${h.name} ${h.branch} ${h.model}`.toLowerCase().includes(fleet.text.toLowerCase()));
  const tr = h => `<tr data-hsid="${esc(h.id)}" tabindex="0"><td>${esc(h.name)}</td><td><span class="mchip m-${modelFamily(h.model)}">${esc(modelShort(h.model) || h.engine)}</span></td><td>${esc(STATE_TEXT[h.state] || h.state)}</td><td>${esc(h.branch)}</td><td class="num">${fmtTokens(h.tokens)}</td><td class="num">${fmtCost(h.cost)}</td><td class="num">${Math.round((h.fill || 0) * 100)}%</td><td class="num">${h.compactions || ""}</td><td class="num">${ago(h.updated)} ago</td></tr>`;
  document.getElementById("main").innerHTML = `${fleetTiles()}<div class="fleet-toolbar"><input id="ftext" type="search" placeholder="Filter sessions" value="${esc(fleet.text)}" aria-label="Filter sessions"><span class="fcount">${rows.length} sessions, last 48 h</span></div>
    <div class="history"><table><thead><tr><th>Session</th><th>Model</th><th>State</th><th>Branch</th><th>Tokens</th><th>Est. cost</th><th>Context</th><th>Compactions</th><th>Updated</th></tr></thead><tbody>${rows.map(tr).join("") || '<tr><td colspan="9">No sessions.</td></tr>'}</tbody></table></div>`;
  wireFleet();
  document.querySelectorAll("[data-hsid]").forEach(el => {
    const open = () => { const c = state.cards.find(x => x.sessions.some(s => s.id === el.dataset.hsid)); if (c) { setView("agents"); openCard(c.key); } };
    el.onclick = open;
    el.onkeydown = e => { if (e.key === "Enter") open(); };
  });
}

function fleetSnapshot() {
  const el = document.activeElement, feed = document.querySelector(".feed ol");
  const typed = el && el.id && /^(INPUT|SELECT)$/.test(el.tagName);
  return {id: typed ? el.id : "", start: typed && el.tagName === "INPUT" ? el.selectionStart : null, feedTop: feed ? feed.scrollTop : 0};
}

function fleetRestore(snap) {
  const feed = document.querySelector(".feed ol");
  if (feed) feed.scrollTop = snap.feedTop;
  const el = snap.id && document.getElementById(snap.id);
  if (!el) return;
  el.focus();
  if (snap.start !== null) el.setSelectionRange(snap.start, snap.start);
}

function rerenderKeepingFocus() {
  const snap = fleetSnapshot();
  view === "history" ? renderHistory() : render();
  fleetRestore(snap);
}

function setWall(on) {
  document.documentElement.classList.toggle("wall", on);
  fleetStore.set("wall", on ? "1" : "0");
  syncNav();
}

function wireFleet() {
  document.querySelectorAll("[data-ffilter]").forEach(b => b.onclick = () => { fleet.filter = b.dataset.ffilter; fleetStore.set("filter", fleet.filter); render(); });
  const sort = document.getElementById("fsort");
  if (sort) sort.onchange = () => { fleet.sort = sort.value; fleetStore.set("sort", fleet.sort); render(); };
  const text = document.getElementById("ftext");
  if (text) text.oninput = () => { fleet.text = text.value; rerenderKeepingFocus(); };
  syncNav();
  document.querySelectorAll(".feed [data-open]").forEach(el => {
    el.onclick = () => openCard(el.dataset.open);
    el.onkeydown = e => { if (e.key === "Enter") openCard(el.dataset.open); };
  });
}

document.addEventListener("keydown", e => {
  const typing = e.target.closest && e.target.closest("input, textarea, select, [contenteditable], .terminal, dialog");
  if (typing || e.ctrlKey || e.metaKey || e.altKey) return;
  if (e.key === "w" && typeof view !== "undefined" && view !== "herdr") { e.preventDefault(); setWall(!document.documentElement.classList.contains("wall")); }
  else if (e.key === "Escape" && document.documentElement.classList.contains("wall") && !(typeof openKey !== "undefined" && openKey)) setWall(false);
});
