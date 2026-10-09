// MOCK AUTH + DATA. Replace with FastAPI calls (e.g. POST /auth/login returning a token, GET /items).
// Hiding buttons here is only for usability. The backend MUST enforce roles and access levels.
const ACCESS = {
  public:     { label: "Public",         icon: "globe" },
  community:  { label: "Community only", icon: "users" },
  restricted: { label: "Restricted",     icon: "lock" },
  sacred:     { label: "Sacred",         icon: "shield-alert" }
};
const USERS = {
  member: { pw: "member123", role: "member", name: "Community member" },
  admin:  { pw: "admin123",  role: "admin",  name: "Admin reviewer" }
};
const CAN = { guest: ["public"], member: ["public", "community"], admin: ["public", "community", "restricted", "sacred"] };
const NEED = { submit: ["member", "admin"], review: ["admin"] };

let items = [
  { id: 1, title: "Sample public item", summary: "Placeholder summary text.", status: "approved", confidence: 0.95, access: "public", source: "Credible source (sample)", by: "Seed data" },
  { id: 2, title: "Sample community item", summary: "Visible to signed-in community members.", status: "approved", confidence: 0.9, access: "community", source: "Elder recording (sample)", by: "Seed data" },
  { id: 3, title: "Sample restricted item", summary: "Visible to admins only for now.", status: "approved", confidence: 0.9, access: "restricted", source: "Custodian (sample)", by: "Seed data" },
  { id: 4, title: "Sample pending item", summary: "AI-generated summary awaiting review.", status: "pending", confidence: 0.62, access: "community", source: "Elder recording (sample)", by: "AI pipeline" }
];
let session = JSON.parse(sessionStorage.getItem("tkr") || "null");
let next = null;
const role = () => (session ? session.role : "guest");
const visible = i => i.status === "approved" && CAN[role()].includes(i.access);

const app = document.getElementById("app");
const esc = s => String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const empty = (icon, text) => `<div class="empty"><div class="big">${ic(icon)}</div><p>${text}</p></div>`;

function toast(msg) {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.classList.add("show");
  setTimeout(() => t.classList.remove("show"), 2500);
}

function card(i, actions = "") {
  const a = ACCESS[i.access];
  const pct = Math.round(i.confidence * 100);
  const level = pct >= 80 ? "high" : pct >= 60 ? "mid" : "low";
  const conf = i.status === "pending"
    ? `<div class="conf ${level}">AI confidence: ${pct}%${level === "low" ? ". Review carefully." : ""}<div class="bar-track"><div style="width:${pct}%"></div></div></div>` : "";
  return `<article class="card ${i.status}">
    <h3>${esc(i.title)}</h3>
    <div class="badges">
      <span class="badge ${i.status}">${i.status[0].toUpperCase() + i.status.slice(1)}</span>
      <span class="badge lvl-${i.access}">${ic(a.icon)} ${a.label}</span>
      <span class="badge">${esc(i.source)}</span>
    </div>
    <p>${esc(i.summary)}</p>
    <div class="meta">Submitted by ${esc(i.by)}</div>
    ${conf}
    ${actions ? `<div class="actions">${actions}</div>` : ""}
  </article>`;
}

const views = {
  search() {
    app.innerHTML = `<h2>Search</h2><p class="sub">${role() === "guest" ? "Showing public items. Log in to see community knowledge." : "Find approved knowledge you have access to."}</p>
      <input id="q" type="search" placeholder="Type to search..." aria-label="Search approved knowledge">
      <div id="results" style="margin-top:1.25rem"></div>`;
    const q = document.getElementById("q");
    const draw = () => {
      const found = items.filter(i => visible(i) && (i.title + " " + i.summary).toLowerCase().includes(q.value.toLowerCase()));
      document.getElementById("results").innerHTML = found.length ? found.map(i => card(i)).join("") : empty("search-x", "No items match your search.");
    };
    q.addEventListener("input", draw);
    draw();
  },
  browse() {
    const list = items.filter(visible);
    app.innerHTML = `<h2>Browse</h2><p class="sub">${list.length} item(s) available to you.</p>` +
      (list.length ? list.map(i => card(i)).join("") : empty("book-x", "Nothing has been approved yet."));
  },
  login() {
    app.innerHTML = `<h2>Log in</h2><p class="sub">Log in to submit knowledge or review submissions.</p>
      <form id="lf" class="form-card">
        <label for="u">Username</label><input id="u" autocomplete="username">
        <label for="p">Password</label><input id="p" type="password" autocomplete="current-password">
        <p class="err" id="err" role="alert"></p>
        <button class="btn" type="submit">Log in</button>
      </form>
      <div class="hint">Demo accounts (mock only): <b>member</b> / member123 and <b>admin</b> / admin123</div>`;
    document.getElementById("lf").onsubmit = e => {
      e.preventDefault();
      const u = USERS[document.getElementById("u").value.trim().toLowerCase()];
      if (!u || u.pw !== document.getElementById("p").value) {
        document.getElementById("err").textContent = "Wrong username or password. Check both and try again.";
        return;
      }
      session = { role: u.role, name: u.name };
      sessionStorage.setItem("tkr", JSON.stringify(session));
      toast("Logged in as " + u.name);
      const go = next || "search"; next = null;
      show(go);
    };
  },
  submit() {
    app.innerHTML = `<h2>Submit</h2><p class="sub">New items go to the review queue. They are not published until an admin approves them.</p>
      <div class="form-card">
        <label for="t">Title</label><input id="t" placeholder="Short title">
        <label for="s">Text or source link</label>
        <textarea id="s" rows="5" placeholder="Paste text or a link to a credible source"></textarea>
        <label for="a">Suggested access level</label>
        <select id="a">${Object.keys(ACCESS).map(k => `<option value="${k}">${ACCESS[k].label}</option>`).join("")}</select>
        <p></p><button class="btn" id="go">Send for review</button>
      </div>`;
    document.getElementById("go").onclick = () => {
      const title = document.getElementById("t").value.trim();
      const text = document.getElementById("s").value.trim();
      if (!title || !text) { toast("Add a title and some text first."); return; }
      items.push({ id: Math.max(0, ...items.map(i => i.id)) + 1, title, summary: text, status: "pending", confidence: 0, access: document.getElementById("a").value, source: "Manual submission", by: session.name });
      toast("Sent for review");
      show(role() === "admin" ? "review" : "browse");
    };
  },
  review() {
    const list = items.filter(i => i.status === "pending");
    app.innerHTML = `<h2>Review queue</h2><p class="sub">${list.length} item(s) waiting for an elder or reviewer.</p>` +
      (list.length
        ? list.map(i => card(i, `<button class="btn approve" data-id="${i.id}" data-s="approved">${ic("check")} Approve</button>
                                 <button class="btn reject" data-id="${i.id}" data-s="rejected">${ic("x")} Reject</button>`)).join("")
        : empty("circle-check", "The queue is empty. Nothing is waiting for review."));
  }
};

app.addEventListener("click", e => {
  const b = e.target.closest("[data-id]");
  if (!b) return;
  if (role() !== "admin") { toast("Only admins can review items."); return; }
  items.find(i => i.id === +b.dataset.id).status = b.dataset.s;
  toast(b.dataset.s === "approved" ? "Item approved and published" : "Item rejected");
  show("review");
});

function chrome() {
  const admin = role() === "admin";
  const pending = items.filter(i => i.status === "pending").length;
  document.getElementById("reviewBtn").hidden = !admin;
  const c = document.getElementById("count");
  c.textContent = pending; c.hidden = pending === 0;
  document.getElementById("auth").innerHTML = session
    ? `<span class="who ${session.role}">${esc(session.name)}</span><button id="lo">${ic("log-out")} Log out</button>`
    : `<button id="li">${ic("log-in")} Log in</button>`;
  const lo = document.getElementById("lo"), li = document.getElementById("li");
  if (lo) lo.onclick = () => { session = null; sessionStorage.removeItem("tkr"); toast("Logged out"); show("search"); };
  if (li) li.onclick = () => show("login");
}

function show(view) {
  if (NEED[view] && !NEED[view].includes(role())) {
    if (role() === "guest") { next = view; toast("Log in to continue."); view = "login"; }
    else { toast("This page is for admins only."); view = "search"; }
  }
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  chrome();
  views[view]();
  window.scrollTo(0, 0);
}

document.querySelectorAll("nav button").forEach(b => b.onclick = () => show(b.dataset.view));
show("search");