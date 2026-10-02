// MOCK DATA - replace with fetch() calls to the FastAPI backend once the contract is agreed
const ACCESS = {
  public:     { label: "Public",         icon: "\u{1F310}" },
  community:  { label: "Community only", icon: "\u{1F465}" },
  restricted: { label: "Restricted",     icon: "\u{1F512}" },
  sacred:     { label: "Sacred",         icon: "\u{26D4}" }
};

let items = [
  { id: 1, title: "Sample approved item", summary: "Placeholder summary text.", status: "approved", confidence: 0.95, access: "public", source: "Credible source (sample)" },
  { id: 2, title: "Sample pending item", summary: "AI-generated summary awaiting review.", status: "pending", confidence: 0.62, access: "community", source: "Elder recording (sample)" }
];

const app = document.getElementById("app");
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2500);
}

function empty(icon, text) {
  return `<div class="empty"><div class="big">${icon}</div><p>${text}</p></div>`;
}

function card(i, actions = "") {
  const a = ACCESS[i.access];
  const pct = Math.round(i.confidence * 100);
  const level = pct >= 80 ? "high" : pct >= 60 ? "mid" : "low";
  const conf = i.status === "pending"
    ? `<div class="conf ${level}">AI confidence: ${pct}%${level === "low" ? " - review carefully" : ""}<div class="bar"><div style="width:${pct}%"></div></div></div>`
    : "";
  return `<article class="card ${i.status}">
    <h3>${esc(i.title)}</h3>
    <div class="badges">
      <span class="badge ${i.status}">${i.status.charAt(0).toUpperCase() + i.status.slice(1)}</span>
      <span class="badge">${a.icon} ${a.label}</span>
      <span class="badge">${esc(i.source)}</span>
    </div>
    <p>${esc(i.summary)}</p>
    ${conf}
    ${actions ? `<div class="actions">${actions}</div>` : ""}
  </article>`;
}

const views = {
  search() {
    app.innerHTML = `<h2>Search</h2><p class="sub">Find approved knowledge items.</p>
      <input id="q" type="search" placeholder="Type to search..." aria-label="Search approved knowledge">
      <div id="results" style="margin-top:1.25rem"></div>`;
    const q = document.getElementById("q");
    const draw = () => {
      const found = items.filter(i => i.status === "approved" &&
        (i.title + " " + i.summary).toLowerCase().includes(q.value.toLowerCase()));
      document.getElementById("results").innerHTML = found.length
        ? found.map(i => card(i)).join("")
        : empty("\u{1F50D}", "No approved items match your search.");
    };
    q.addEventListener("input", draw);
    draw();
  },
  browse() {
    const list = items.filter(i => i.status === "approved");
    app.innerHTML = `<h2>Browse</h2><p class="sub">${list.length} approved item(s).</p>` +
      (list.length ? list.map(i => card(i)).join("") : empty("\u{1F4D6}", "Nothing has been approved yet."));
  },
  submit() {
    app.innerHTML = `<h2>Submit</h2><p class="sub">New items go to the review queue. They are not published until approved.</p>
      <div class="form-card">
        <label for="t">Title</label>
        <input id="t" placeholder="Short title">
        <label for="s">Text or source link</label>
        <textarea id="s" rows="5" placeholder="Paste text or a link to a credible source"></textarea>
        <label for="a">Suggested access level</label>
        <select id="a">${Object.keys(ACCESS).map(k => `<option value="${k}">${ACCESS[k].icon} ${ACCESS[k].label}</option>`).join("")}</select>
        <p></p>
        <button class="btn submit" id="go">Submit for review</button>
      </div>`;
    document.getElementById("go").onclick = () => {
      const title = document.getElementById("t").value.trim();
      const text = document.getElementById("s").value.trim();
      if (!title || !text) { toast("Please fill in the title and text."); return; }
      items.push({ id: items.length + 1, title, summary: text, status: "pending", confidence: 0, access: document.getElementById("a").value, source: "Manual submission" });
      toast("Submitted for review");
      show("review");
    };
  },
  review() {
    const list = items.filter(i => i.status === "pending");
    app.innerHTML = `<h2>Review queue</h2><p class="sub">Quarantine: ${list.length} item(s) waiting for an elder or reviewer.</p>` +
      (list.length
        ? list.map(i => card(i, `<button class="btn approve" onclick="setStatus(${i.id},'approved')">&#10003; Approve</button>
                                 <button class="btn reject" onclick="setStatus(${i.id},'rejected')">&#10005; Reject</button>`)).join("")
        : empty("\u{2705}", "The queue is empty. Nothing is waiting for review."));
  }
};

function setStatus(id, status) {
  items.find(i => i.id === id).status = status;
  toast(status === "approved" ? "Item approved and published" : "Item rejected");
  show("review");
}

function show(view) {
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  const pending = items.filter(i => i.status === "pending").length;
  const c = document.getElementById("count");
  c.textContent = pending;
  c.hidden = pending === 0;
  views[view]();
  window.scrollTo(0, 0);
}

document.querySelectorAll("nav button").forEach(b => b.onclick = () => show(b.dataset.view));
show("search");
