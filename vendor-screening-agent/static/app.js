/* Vendor Screening Agent - dashboard logic (v6, friendly UI) */
"use strict";

const $ = (id) => document.getElementById(id);
let lastQuery = null;

const DECISION_TEXT = {
  "Likely duplicate": "Already exists",
  "Human review": "Worth a review",
  "Likely new": "Looks new",
};

/* ---------- helpers ---------- */
function esc(s){
  return String(s == null ? "" : s)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
function bandColor(conf){
  return conf === "HIGH" ? "var(--match)" : (conf === "MEDIUM" ? "var(--rev)" : "var(--new)");
}
function toast(msg){
  const t = $("toast");
  t.textContent = msg; t.hidden = false;
  requestAnimationFrame(() => t.classList.add("show"));
  clearTimeout(toast._t);
  toast._t = setTimeout(() => { t.classList.remove("show"); setTimeout(() => { t.hidden = true; }, 260); }, 2800);
}

/* ---------- rendering ---------- */
function signals(ev){
  if(!ev) return "";
  const map = [
    ["Name", ev.name_similarity], ["Location", ev.country_address],
    ["Registry", ev.registry_identifier], ["Website", ev.website_domain],
    ["Web", ev.external_evidence],
  ];
  const pills = map
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => `<span class="sig">${k} <b>${v.toFixed(0)}%</b></span>`);
  return pills.length ? `<div class="signals">${pills.join("")}</div>` : "";
}
function details(list){
  if(!list || !list.length) return "";
  return `<div class="details"><h4>Company details</h4>${
    list.map(d => `<div class="drow"><span class="dk">${esc(d.label)}</span><span class="dv">${esc(d.value)}</span></div>`).join("")
  }</div>`;
}
function why(items, add){
  let html = "";
  if(items && items.length){
    html += `<div class="why"><h4>Why it matches</h4><ul>${
      items.map(i => `<li>${esc(i)}</li>`).join("")}</ul></div>`;
  }
  if(add && add.length){
    html += `<div class="addnote">${esc(add.join(" · "))}</div>`;
  }
  return html;
}
function renderVat(v){
  if(!v || !v.checked) return "";
  if(v.valid === true){
    return `<div class="vat ok">✅ <b>VAT verified by EU VIES</b>${v.name ? " — " + esc(v.name) : ""}
      <span class="vsrc">official EU source · ${esc(v.vat)}</span></div>`;
  }
  if(v.valid === false){
    return `<div class="vat bad">⚠️ <b>VAT number not found in EU VIES</b> (${esc(v.vat)}) — may be invalid.</div>`;
  }
  return `<div class="vat warn">VAT check unavailable right now (${esc(v.vat || "")}).</div>`;
}
function renderVerdict(data){
  const list = data.candidates || [];
  if(!list.length){
    return `<div class="verdict v-new"><div class="vicon">✨</div><div>
      <div class="vhead">Looks like a new supplier</div>
      <div class="vsub">We didn't find a close match in your list or public records — it's safe to add.</div>
    </div></div>`;
  }
  const t = list[0];
  const who = `${esc(t.vendor_name || "this company")}`;
  const pct = t.match_percent.toFixed(0);
  if(t.decision_label === "Likely duplicate"){
    return `<div class="verdict v-dup"><div class="vicon">↩</div><div>
      <div class="vhead">This supplier already exists</div>
      <div class="vsub">Best match is <b>${who}</b> (${pct}% match). Reuse the existing record instead of creating a duplicate.</div>
    </div></div>`;
  }
  if(t.decision_label === "Human review"){
    return `<div class="verdict v-review"><div class="vicon">🔍</div><div>
      <div class="vhead">Worth a quick review</div>
      <div class="vsub"><b>${who}</b> looks close (${pct}% match) but isn't a certain match. Have someone confirm before adding.</div>
    </div></div>`;
  }
  return `<div class="verdict v-new"><div class="vicon">✨</div><div>
    <div class="vhead">Probably a new supplier</div>
    <div class="vsub">The closest match is only ${pct}% — no strong duplicate found.</div>
  </div></div>`;
}
function card(c, i){
  const loc = [c.city, c.country].filter(Boolean).join(", ");
  const isInternal = c.source[0].startsWith("Vendor master");
  const srcLabel = isInternal ? "In your supplier list" : "Verified in public registry";
  const color = bandColor(c.confidence);
  const pct = c.match_percent;
  const C = 201.06;                              // 2*pi*32 (r=32 in a 70px svg)
  const off = C * (1 - pct / 100);
  return `<div class="card ${i === 0 ? "best" : ""}">
    <div class="chead">
      <div class="gauge">
        <svg viewBox="0 0 70 70">
          <circle class="gtrack" cx="35" cy="35" r="32"></circle>
          <circle class="gfill" cx="35" cy="35" r="32" stroke="${color}"
                  stroke-dasharray="${C}" stroke-dashoffset="${C}" data-off="${off.toFixed(1)}"></circle>
        </svg>
        <span class="gv" style="color:${color}" data-pct="${pct}">0</span>
      </div>
      <div class="who">
        <div class="cname">${esc(c.vendor_name || "(unnamed)")}</div>
        <div class="cmeta">${esc(loc || "-")}${c.vendor_id ? " · " + esc(c.vendor_id) : ""}</div>
        <span class="decision-badge rag-${c.confidence}">${esc(DECISION_TEXT[c.decision_label] || c.decision_label)}</span>
      </div>
    </div>
    <div class="srcline"><span class="sdot ${isInternal ? "" : "reg"}"></span>${srcLabel}</div>
    ${why(c.similar, c.add_on)}
    ${details(c.details)}
    ${signals(c.evidence)}
    <div class="actions" data-id="${esc(c.vendor_id || "")}" data-name="${esc(c.vendor_name || "")}" data-pct="${pct}">
      <button class="btn-reuse"  data-decision="reuse">Reuse existing</button>
      <button class="btn-review" data-decision="review">Review</button>
      <button class="btn-create" data-decision="create">Create new</button>
    </div>
  </div>`;
}
/* animate ring gauges (stroke) + count-up numbers after they're in the DOM */
function animateGauges(){
  document.querySelectorAll(".gfill").forEach(el => {
    const off = parseFloat(el.dataset.off || "0");
    requestAnimationFrame(() => { el.style.strokeDashoffset = off; });
  });
  document.querySelectorAll(".gv").forEach(el => {
    const target = parseFloat(el.dataset.pct || "0");
    const start = performance.now(), dur = 1000;
    function step(now){
      const t = Math.min(1, (now - start) / dur);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = Math.round(target * eased);
      if(t < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  });
}

function renderCards(list){
  if(!list.length){
    return `<div class="empty"><span class="empty-icon">✨</span>
      <h3>No matches found</h3><p>This looks like a new supplier - safe to add.</p></div>`;
  }
  return `<div class="grid">${list.map(card).join("")}</div>`;
}
function renderWeb(w){
  if(!w) return "";
  let body;
  if(!w.ok) body = `<p class="muted-note">Web check unavailable right now.</p>`;
  else if(!w.results.length) body = `<p class="muted-note">No web results found.</p>`;
  else body = w.results.map(r =>
    `<div class="web-item"><a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>
      <span class="url">${esc(r.url)}</span>${esc(r.snippet)}</div>`).join("");
  return `<div class="web"><h4>Web check ${w.from_cache ? "(cached)" : ""}</h4>${body}</div>`;
}

/* ---------- recent decisions ---------- */
async function refreshDecisions(){
  try{
    const data = await (await fetch("/decisions?limit=15")).json();
    const el = $("decisionsList");
    if(!data.count){ el.innerHTML = '<p class="muted-note">No decisions yet.</p>'; return; }
    el.innerHTML = data.decisions.map(d => `
      <div class="decision-item">
        <span class="lbl ${esc(d.decision)}">${esc(d.decision_label)}</span>
        &middot; ${esc(d.candidate_vendor_name || d.query_vendor_name)}
        <div class="meta">${esc(d.candidate_vendor_id || "")} · ${esc((d.timestamp||"").slice(0,16).replace("T"," "))}</div>
      </div>`).join("");
  }catch(_){ /* non-fatal */ }
}

/* ---------- decision buttons (functional) ---------- */
document.addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-decision]");
  if(!btn || !lastQuery) return;
  const group = btn.closest(".actions");
  const decision = btn.dataset.decision;
  group.querySelectorAll("button").forEach(b => b.disabled = true);

  const payload = {
    query_vendor_name: lastQuery.vendor_name,
    query_country: lastQuery.country,
    query_website: lastQuery.website,
    candidate_vendor_id: group.dataset.id,
    candidate_vendor_name: group.dataset.name,
    match_percent: parseFloat(group.dataset.pct) || 0,
    decision: decision,
  };
  try{
    const data = await (await fetch("/decision", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    })).json();
    if(!data.ok) throw new Error(data.error || "Failed");

    let msg;
    if(decision === "reuse")
      msg = `✓ Reused ${group.dataset.name || "existing supplier"} — no duplicate created.`;
    else if(decision === "review")
      msg = `✓ Sent for review — a colleague will confirm this supplier.`;
    else
      msg = `✓ New supplier added${data.created_vendor ? " (" + data.created_vendor.vendor_id + ")" : ""}.`;

    const note = document.createElement("div");
    note.className = "decided " + decision;
    note.textContent = msg;
    group.replaceWith(note);
    toast(msg);
    refreshDecisions();
    $("decisionsPanel").open = true;
  }catch(err){
    const note = document.createElement("div");
    note.className = "decided err";
    note.textContent = "Could not save: " + err.message;
    group.after(note);
    group.querySelectorAll("button").forEach(b => b.disabled = false);
  }
});

/* ---------- search ---------- */
$("demoChips").addEventListener("click", (e) => {
  const chip = e.target.closest(".chip");
  if(!chip) return;
  $("vendor_name").value = chip.dataset.n;
  $("country").value = chip.dataset.c;
  $("website").value = "";
  $("tax_id").value = chip.dataset.t || "";
  $("searchForm").requestSubmit();
});

$("searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = $("submitBtn"), pane = $("resultsPane");
  btn.disabled = true; btn.textContent = "Checking…";
  pane.innerHTML = `<div class="spin"><div class="ring"></div>Checking your suppliers and public company records…</div>`;

  const payload = {
    vendor_name: $("vendor_name").value.trim(),
    country: $("country").value.trim(),
    website: $("website").value.trim(),
    tax_id: $("tax_id").value.trim(),
  };
  lastQuery = payload;
  try{
    const res = await fetch("/screen", {
      method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(payload),
    });
    if(!res.ok) throw new Error("Check failed (" + res.status + ")");
    const data = await res.json();
    pane.innerHTML =
      renderVerdict(data) + renderVat(data.vat_check) +
      `<h3 class="sec">Matches found (${data.result_count})</h3>` +
      renderCards(data.candidates) + renderWeb(data.web_search_fallback);
    animateGauges();
  }catch(err){
    pane.innerHTML = `<div class="error">${esc(err.message)}. Please try again.</div>`;
  }finally{
    btn.disabled = false; btn.textContent = "Check now";
  }
});

/* deep link: /?q=IBM&c=United+States auto-runs a check */
window.addEventListener("DOMContentLoaded", () => {
  refreshDecisions();
  const p = new URLSearchParams(location.search);
  if(p.get("q")){
    $("vendor_name").value = p.get("q");
    $("country").value = p.get("c") || "";
    $("website").value = p.get("w") || "";
    $("tax_id").value = p.get("t") || "";
    $("searchForm").requestSubmit();
  }
});
