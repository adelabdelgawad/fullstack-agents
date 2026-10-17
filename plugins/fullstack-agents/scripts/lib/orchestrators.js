// Orchestrator wall: a sidebar of orchestrators and one card per orchestrator with its plan, workers and usage.
const orc = {collapsed: fleetStore.get("orc-collapsed", "0") === "1", tpm: new Map()};
const openOrc = () => (typeof openKey !== "undefined" && openKey) || "";

const orcState = c => {
  if (needsHuman(c)) return {key: "waiting", label: "Waiting · needs you", icon: "⏸"};
  if (isRunning(c)) return {key: "running", label: "Running", icon: "▶"};
  if (isStale(c)) return {key: "stale", label: "Stale · no output for 5+ min", icon: "◌"};
  if (c.phase === "complete") return {key: "done", label: "Done", icon: "✓"};
  return {key: "idle", label: "Idle", icon: "■"};
};
const BRANCH_ICON = '<svg viewBox="0 0 16 16" aria-hidden="true"><path fill="currentColor" d="M5 3.25a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm0 9.5a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0Zm7-7a.75.75 0 1 1-1.5 0 .75.75 0 0 1 1.5 0ZM4.25 1a2.25 2.25 0 0 0-.75 4.37v5.26a2.25 2.25 0 1 0 1.5 0V9.5c.5.3 1.1.5 1.75.5h1.5a2.25 2.25 0 0 0 2.12-1.5 2.25 2.25 0 1 0-1.5-.88A.75.75 0 0 1 8.25 8.5h-1.5A1.75 1.75 0 0 1 5 6.75V5.37A2.25 2.25 0 0 0 4.25 1Z"/></svg>';
const homePath = p => String(p || "").replace(/^\/home\/[^/]+/, "~");
const modelChip = m => m ? `<span class="mchip m-${modelFamily(m)}" title="${esc(m)}">${esc(modelShort(m))}</span>` : "";

function orcPlan(c) {
  const t = (c.sessions || []).map(s => s.task_tracking).find(x => x && !x.error && x.total);
  if (t) {
    const cur = t.items.find(taskIsActive) || t.items.find(x => x.status === "in_progress");
    return {title: [t.title, cur && cur.title].filter(Boolean).join(" · "), done: t.completed, total: t.total};
  }
  if (c.steps && c.steps.length) return {title: (activeStep(c) || {}).text || "Lead steps", done: stepsDone(c), total: c.steps.length};
  const briefs = c.rounds || [];
  if (briefs.length) return {title: c.label || c.goal || "Implementer briefs", done: briefs.filter(r => r.state === "done").length, total: briefs.length};
  return null;
}

function orcWorkers(c) {
  const runs = (c.runs || []).map(r => r.state);
  const agents = cardAgents(c).filter(a => !a.shell).map(a => a.state);
  const all = [...runs, ...agents], n = st => all.filter(x => st.includes(x)).length;
  return {total: all.length, running: n(["running"]), done: n(["done", "completed"]), failed: n(["failed", "abandoned"])};
}

function noteCardTpm() {
  for (const c of (state && state.cards) || []) {
    const pts = orc.tpm.get(c.key) || [];
    pts.push((c.usage && c.usage.tpm) || 0);
    if (pts.length > 40) pts.shift();
    orc.tpm.set(c.key, pts);
  }
}

function orcSidebar(cards) {
  const count = k => cards.filter(c => orcState(c).key === k).length;
  const row = c => {
    const st = orcState(c), plan = orcPlan(c), w = orcWorkers(c), u = c.usage || {};
    const pct = plan ? Math.round(plan.done / Math.max(plan.total, 1) * 100) : 0;
    return `<button class="orc-row${openOrc() === c.key ? " sel" : ""} st-${st.key}" data-orc="${esc(c.key)}" aria-current="${openOrc() === c.key}" title="${esc(c.title)} — ${esc(st.label)}">
      <span class="orc-row-top"><span class="dot" aria-hidden="true"></span><b>${esc(c.title)}</b>${u.compactions ? `<span class="cbadge">${u.compactions}×</span>` : ""}${modelChip(u.model)}</span>
      <span class="orc-row-sub">${plan ? esc(`${plan.done}/${plan.total} plan`) : "no plan"}<span>${w.total ? `${w.done}/${w.total} workers` : ""}</span></span>
      <span class="orc-mini" aria-hidden="true"><span style="width:${pct}%"></span></span></button>`;
  };
  return `<nav class="orc-side${orc.collapsed ? " collapsed" : ""}" aria-label="Orchestrators">
    <div class="orc-side-head"><span>Orchestrators</span><span class="fcount">${cards.length}</span><button class="tbtn orc-collapse" id="orc-collapse" aria-label="${orc.collapsed ? "Expand" : "Collapse"} orchestrator list">${orc.collapsed ? "›" : "‹"}</button></div>
    <button class="orc-row orc-all${openOrc() ? "" : " sel"}" data-orc="" aria-current="${!openOrc()}"><b>All orchestrators</b><span class="orc-row-sub">${count("running")} running · ${count("waiting")} waiting · ${count("stale")} stale</span></button>
    ${cards.map(row).join("")}</nav>`;
}

function orcCard(c) {
  const st = orcState(c), plan = orcPlan(c), w = orcWorkers(c), u = c.usage, lead = (c.sessions || [])[0] || {};
  const branch = c.tree ? c.tree.branch : lead.branch, dirty = gitBadge(c), cwd = c.worktree || c.repo;
  const flag = c.needs_you.length ? FLAG_TEXT[c.needs_you[0]] || c.needs_you[0] : "";
  const pct = plan ? Math.round(plan.done / Math.max(plan.total, 1) * 100) : 0;
  const metric = (label, value, extra = "") => `<div class="orc-m"><span>${label}</span><b>${value}</b>${extra}</div>`;
  const ctxTone = u ? (u.fill >= 0.9 ? "bad" : u.fill >= 0.8 ? "warn" : "") : "";
  const respond = st.key === "waiting" ? `<button class="tbtn orc-respond" data-respond="${esc(c.key)}">Respond</button>` : "";
  return `<article class="card orc st-${st.key}${u && u.blowout ? " blowout" : ""}${openOrc() === c.key ? " open-here" : ""}" tabindex="0" data-key="${esc(c.key)}" data-sid="${esc(lead.id || "")}">
    <header class="orc-head"><span class="orc-ico" aria-hidden="true">${st.icon}</span><h3 title="${esc(c.title)}">${esc(c.title)}</h3>${modelChip(u && u.model || lead.model)}<button class="star" data-fav="${esc(c.key)}" aria-pressed="${!!c.favourite}" aria-label="${c.favourite ? "Remove from favourites" : "Add to favourites"}">${c.favourite ? "★" : "☆"}</button></header>
    <div class="orc-meta"><span class="orc-role">orchestrator · ${esc(lead.engine || "claude")}</span><span class="stage">${esc(STAGE_LABEL(c))}</span>${c.sessions.length > 1 ? `<span>${c.sessions.length} sessions</span>` : ""}</div>
    <div class="orc-path" title="${esc(cwd)}">${esc(homePath(cwd))}</div>
    <div class="orc-git"><span class="br" title="branch">${BRANCH_ICON}${esc(branch || "no branch")}</span><span class="chip">${c.worktree && c.worktree !== c.repo ? "worktree" : "main checkout"}</span><span class="${dirty ? "dirty" : "clean"}">${dirty ? `${dirty} modified` : "clean"}</span></div>
    <div class="orc-plan">${plan ? `<div class="orc-plan-t"><span title="${esc(plan.title)}">${esc(plan.title)}</span><b>${plan.done}/${plan.total}</b></div><div class="orc-bar" aria-hidden="true"><span style="width:${pct}%"></span></div>` : '<div class="orc-plan-t muted">No plan reported. Workers launched ad hoc.</div>'}
      ${questionLine(c) || cardNow(c)}</div>
    <div class="orc-workers">${squaresHtml(c)}<div class="orc-wsum"><span>${w.total ? `${w.running} running · ${w.done} done${w.failed ? ` · <span class="bad">${w.failed} failed</span>` : ""}` : "no workers"}</span>${sparkline(orc.tpm.get(c.key) || [])}</div></div>
    <div class="orc-metrics">${metric("Cost", esc(fmtCost(u && u.cost)))}${metric("Tokens", esc(fmtTokens(u && u.tokens)))}${metric("Updated", esc(ago(c.updated)))}${metric(`Context${u && u.compactions ? ` <span class="cbadge">${u.compactions}×</span>` : ""}`, u ? `<span class="${ctxTone}">${Math.round(u.fill * 100)}%</span>` : "—", u ? `<span class="orc-bar ctx-${ctxTone || "ok"}"><span style="width:${Math.round(u.fill * 100)}%"></span></span>` : "")}</div>
    <footer class="orc-status"><span aria-hidden="true">${st.icon}</span><span>${esc(st.label)}</span>${flag ? `<span class="flag">${esc(flag)}</span>` : ""}${respond}</footer></article>`;
}

function orcWall(cards) {
  return `<div class="orc-grid">${cards.map(orcCard).join("") || '<div class="none">No orchestrators match.</div>'}</div>`;
}

function mountOrchestrators(cards, total) {
  const main = document.getElementById("main"), pnl = panel();
  const inline = document.documentElement.classList.contains("split") && matchMedia("(min-width: 1101px)").matches;
  const sig = [inline, fleet.feed].join();
  if (main.dataset.sig !== sig || !document.getElementById("orc-cards")) {
    if (main.contains(pnl)) document.body.appendChild(pnl);
    main.innerHTML = `<div id="fleet-top"></div><div class="orc-shell${fleet.feed && !inline ? " with-feed" : ""}${inline ? " inline-detail" : ""}"><div id="orc-side-wrap"></div><div class="orc-main"><div id="orc-cards"></div></div>${inline ? '<div class="orc-detail" id="orc-detail"></div>' : '<div id="feed-wrap"></div>'}</div><div id="orc-legend"></div>`;
    main.dataset.sig = sig;
  }
  setIfChanged("fleet-top", fleetTiles() + fleetToolbar(cards.length, total));
  setIfChanged("orc-side-wrap", orcSidebar(cards));
  setIfChanged("orc-cards", orcWall(cards));
  setIfChanged("orc-legend", legendHtml());
  if (!inline) setIfChanged("feed-wrap", feedHtml());
  const slot = document.getElementById("orc-detail");
  if (slot && pnl.parentNode !== slot) slot.appendChild(pnl);
  if (!slot && pnl.parentNode !== document.body) document.body.appendChild(pnl);
}

function respondTo(key) {
  const c = state.cards.find(x => x.key === key), sid = ((c && c.now) || [])[0]?.id;
  tab2 = sid && ((state.session_panes || {})[sid]) ? "terminal" : "info";
  openCard(key, true);
}

function wireOrchestrators() {
  document.querySelectorAll("[data-orc]").forEach(b => b.onclick = () => {
    if (b.dataset.orc) openCard(b.dataset.orc, true); else closePanel();
  });
  const col = document.getElementById("orc-collapse");
  if (col) col.onclick = () => { orc.collapsed = !orc.collapsed; fleetStore.set("orc-collapsed", orc.collapsed ? "1" : "0"); render(); };
  document.querySelectorAll("[data-respond]").forEach(b => {
    b.onclick = ev => { ev.stopPropagation(); respondTo(b.dataset.respond); };
    b.onkeydown = ev => ev.stopPropagation();
  });
}
