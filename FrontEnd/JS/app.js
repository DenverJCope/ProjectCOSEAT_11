// Traditional Knowledge Repository - review frontend
// Wired to the FastAPI backend in API/app.py. Served same-origin, so fetch("/api/...").
// Replaces the earlier mock-data version now that the ingest pipeline + API exist.

const API = "";  // same origin (served by FastAPI). Set to "http://127.0.0.1:8000" if serving separately.

const ACCESS = {
  public:     { label: "Public",         icon: "\u{1F310}" },
  community:  { label: "Community only", icon: "\u{1F465}" },
  restricted: { label: "Restricted",     icon: "\u{1F512}" },
  sacred:     { label: "Sacred",          icon: "\u{26D4}" }
};

const app = document.getElementById("app");
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// remember who is reviewing (per browser) so the audit trail records it
function reviewerName() {
  let n = "";
  try { n = localStorage.getItem("tkr_reviewer") || ""; } catch (e) { /* private mode */ }
  if (!n) {
    n = (prompt("Your name (recorded against each review decision):") || "").trim() || "Reviewer";
    try { localStorage.setItem("tkr_reviewer", n); } catch (e) { /* ignore */ }
  }
  return n;
}

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2500);
}

function empty(icon, text) {
  return `<div class="empty"><div class="big">${icon}</div><p>${text}</p></div>`;
}

async function api(path, opts) {
  const res = await fetch(API + path, opts);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function badge(txt, cls = "") { return `<span class="badge ${cls}">${esc(txt)}</span>`; }

function accessSelect(id, current) {
  return `<select id="acc-${id}" aria-label="Access level">` +
    Object.keys(ACCESS).map(k =>
      `<option value="${k}" ${k === current ? "selected" : ""}>${ACCESS[k].icon} ${ACCESS[k].label}</option>`
    ).join("") + `</select>`;
}

// card for an item waiting in the review queue
function reviewCard(i) {
  const pct = Math.round((i.confidence || 0) * 100);
  const level = pct >= 60 ? "high" : pct >= 25 ? "mid" : "low";
  const flagged = i.status === "needs_review";
  return `<article class="card pending">
    <h3>${esc(i.title)}</h3>
    <div class="badges">
      ${badge(flagged ? "Needs review (low relevance)" : "Pending", "pending")}
      ${badge(i.source)}
      ${badge((i.summary_method || "") + " summary")}
    </div>
    <div class="conf ${level}">Relevance to scope: ${pct}%
      <div class="bar"><div style="width:${pct}%"></div></div></div>
    <label>Summary (preview - editable)</label>
    <textarea id="sum-${i.id}" rows="3">${esc(i.summary)}</textarea>
    <label>Source text (what will be stored and cited - editable)</label>
    <textarea id="src-${i.id}" rows="6">${esc(i.original_text)}</textarea>
    <label>Access level</label>
    ${accessSelect(i.id, i.access)}
    <div class="actions" style="margin-top:.9rem">
      <button class="btn approve" data-approve="${i.id}">&#10003; Approve &amp; add to repository</button>
      <button class="btn reject" data-reject="${i.id}">&#10005; Reject</button>
    </div>
  </article>`;
}

// card for an approved item (search / browse)
function approvedCard(i) {
  const a = ACCESS[i.access] || ACCESS.community;
  return `<article class="card">
    <h3>${esc(i.title)}</h3>
    <div class="badges">${badge("Approved", "approved")} ${badge(a.icon + " " + a.label)} ${badge(i.source)}</div>
    <p>${esc(i.summary)}</p>
    <details><summary>Source text</summary><p style="white-space:pre-wrap">${esc(i.original_text)}</p></details>
  </article>`;
}

const views = {
  async search() {
    app.innerHTML = `<h2>Ask</h2><p class="sub">Answers come only from approved sources, shown word for word with their citation. If nothing approved is relevant, the system says so rather than guessing.</p>
      <div style="display:flex; gap:.6rem">
        <input id="ask" type="search" placeholder="Ask a question..." aria-label="Ask a question" style="flex:1">
        <button class="btn primary" id="askgo">Ask</button>
      </div>
      <div id="answer" style="margin-top:1.25rem"></div>
      <h2 style="margin-top:2rem">Browse by keyword</h2>
      <input id="q" type="search" placeholder="Filter approved items..." aria-label="Filter approved knowledge">
      <div id="results" style="margin-top:1rem"></div>`;

    // --- Ask (retrieval with citations / abstain) ---
    const askBox = document.getElementById("ask");
    const runAsk = async () => {
      const query = askBox.value.trim();
      if (!query) return;
      const box = document.getElementById("answer");
      box.innerHTML = `<p class="sub">Searching approved sources...</p>`;
      try {
        const r = await api("/api/ask?q=" + encodeURIComponent(query));
        if (r.abstained) {
          box.innerHTML = `<div class="card" style="border-left-color:var(--amber)">
            <h3>Not enough information</h3>
            <p>No approved source is relevant enough to answer this safely. ${esc(r.reason || "")}</p>
            <p class="sub">This is deliberate: the repository will not guess.</p></div>`;
          return;
        }
        box.innerHTML = r.passages.map(p => `<article class="card">
          <p>${esc(p.snippet)}</p>
          <details><summary>Full source passage</summary><p style="white-space:pre-wrap">${esc(p.source_text)}</p></details>
          <div class="badges" style="margin-top:.6rem">${badge("Source: " + p.citation)} ${badge("match " + Math.round(p.score * 100) + "%")}</div>
        </article>`).join("");
      } catch (e) { box.innerHTML = empty("\u{26A0}", "Could not reach the API."); }
    };
    document.getElementById("askgo").onclick = runAsk;
    askBox.addEventListener("keydown", e => { if (e.key === "Enter") runAsk(); });

    // --- keyword browse (client-side filter over approved) ---
    let all = [];
    try { all = await api("/api/approved"); } catch (e) { document.getElementById("results").innerHTML = empty("\u{26A0}", "Could not reach the API."); return; }
    const q = document.getElementById("q");
    const draw = () => {
      const term = q.value.toLowerCase();
      const found = all.filter(i => (i.title + " " + i.summary + " " + i.original_text).toLowerCase().includes(term));
      document.getElementById("results").innerHTML = term
        ? (found.length ? found.map(approvedCard).join("") : empty("\u{1F50D}", "No approved items match."))
        : "";
    };
    q.addEventListener("input", draw);
  },

  async browse() {
    app.innerHTML = `<h2>Browse</h2><p class="sub">Loading...</p>`;
    let list = [];
    try { list = await api("/api/approved"); } catch (e) { app.innerHTML = `<h2>Browse</h2>` + empty("\u{26A0}", "Could not reach the API."); return; }
    app.innerHTML = `<h2>Browse</h2><p class="sub">${list.length} approved item(s).</p>` +
      (list.length ? list.map(approvedCard).join("") : empty("\u{1F4D6}", "Nothing has been approved yet."));
  },

  submit() {
    app.innerHTML = `<h2>Submit</h2><p class="sub">New items go to the review queue. Nothing is published until an elder or reviewer approves it.</p>
      <div class="form-card">
        <label for="t">Title</label>
        <input id="t" placeholder="Short title">
        <label for="s">Text or source</label>
        <textarea id="s" rows="5" placeholder="Paste the text to be recorded"></textarea>
        <label for="a">Suggested access level</label>
        ${accessSelect("new", "community")}
        <p></p>
        <button class="btn submit" id="go">Submit for review</button>
      </div>`;
    document.getElementById("go").onclick = async () => {
      const title = document.getElementById("t").value.trim();
      const text = document.getElementById("s").value.trim();
      if (!title || !text) { toast("Please fill in the title and text."); return; }
      try {
        await api("/api/submit", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ title, text, access: document.getElementById("acc-new").value })
        });
        toast("Submitted for review");
        show("review");
      } catch (e) { toast("Submit failed: " + e.message); }
    };
  },

  async review() {
    app.innerHTML = `<h2>Review queue</h2><p class="sub">Loading...</p>`;
    let list = [];
    try { list = await api("/api/pending"); } catch (e) { app.innerHTML = `<h2>Review queue</h2>` + empty("\u{26A0}", "Could not reach the API."); return; }
    app.innerHTML = `<h2>Review queue</h2><p class="sub">${list.length} item(s) waiting for an elder or reviewer. Nothing enters the repository until approved.</p>` +
      (list.length ? list.map(reviewCard).join("") : empty("\u{2705}", "The queue is empty."));

    app.querySelectorAll("[data-approve]").forEach(b => b.onclick = () => decide(b.dataset.approve, "approve"));
    app.querySelectorAll("[data-reject]").forEach(b => b.onclick = () => decide(b.dataset.reject, "reject"));
  }
};

async function decide(id, action) {
  const who = reviewerName();
  try {
    if (action === "approve") {
      const summary = document.getElementById(`sum-${id}`).value;
      const original_text = document.getElementById(`src-${id}`).value;
      const access = document.getElementById(`acc-${id}`).value;
      await api(`/api/items/${id}/approve`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewed_by: who, access, summary, original_text })
      });
      toast("Approved and added to the repository");
    } else {
      const reason = prompt("Reason for rejecting (optional):") || "";
      await api(`/api/items/${id}/reject`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reviewed_by: who, reason })
      });
      toast("Rejected");
    }
    await refreshCount();
    views.review();
  } catch (e) { toast("Action failed: " + e.message); }
}

async function refreshCount() {
  try {
    const s = await api("/api/stats");
    const c = document.getElementById("count");
    c.textContent = s.pending;
    c.hidden = s.pending === 0;
  } catch (e) { /* ignore */ }
}

function show(view) {
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  views[view]();
  refreshCount();
  window.scrollTo(0, 0);
}

document.querySelectorAll("nav button").forEach(b => b.onclick = () => show(b.dataset.view));
show("search");
