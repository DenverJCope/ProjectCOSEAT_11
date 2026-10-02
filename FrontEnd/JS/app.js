// MOCK DATA - replace with fetch() calls to the FastAPI backend once the contract is agreed
let items = [
  { id: 1, title: "Sample approved item", summary: "Placeholder summary text.", status: "approved", confidence: 0.95 },
  { id: 2, title: "Sample pending item", summary: "AI-generated summary awaiting review.", status: "pending", confidence: 0.62 }
];

const app = document.getElementById("app");

function card(i, actions = "") {
  return `<div class="card"><h3>${i.title}</h3><p>${i.summary}</p>
  <p class="status">Status: ${i.status} | Confidence: ${i.confidence}</p>${actions}</div>`;
}

const views = {
  search() {
    app.innerHTML = `<h2>Search</h2><input id="q" placeholder="Search approved knowledge"><div id="results"></div>`;
    const q = document.getElementById("q");
    const draw = () => {
      document.getElementById("results").innerHTML = items
        .filter(i => i.status === "approved" && (i.title + i.summary).toLowerCase().includes(q.value.toLowerCase()))
        .map(i => card(i)).join("");
    };
    q.addEventListener("input", draw);
    draw();
  },
  browse() {
    app.innerHTML = "<h2>Browse</h2>" + items.filter(i => i.status === "approved").map(i => card(i)).join("");
  },
  submit() {
    app.innerHTML = `<h2>Submit</h2>
      <input id="t" placeholder="Title">
      <textarea id="s" rows="5" placeholder="Text or source link"></textarea>
      <button id="go">Submit for review</button>`;
    document.getElementById("go").onclick = () => {
      items.push({ id: items.length + 1, title: t.value, summary: s.value, status: "pending", confidence: 0 });
      views.review();
    };
  },
  review() {
    app.innerHTML = "<h2>Review queue (quarantine)</h2>" + items.filter(i => i.status === "pending")
      .map(i => card(i, `<button onclick="setStatus(${i.id},'approved')">Approve</button>
                         <button onclick="setStatus(${i.id},'rejected')">Reject</button>`)).join("");
  }
};

function setStatus(id, status) {
  items.find(i => i.id === id).status = status;
  views.review();
}

document.querySelectorAll("nav button").forEach(b => b.onclick = () => views[b.dataset.view]());
views.search();
