/* JoMapView — the embedded Floorplan map, shown inside the chat page.
 * Data comes from the backend GET /v1/floorplan (preferred) or the static
 * floorplan/graph.json. No dependencies; uses the GUI's existing CSS vars.
 */
(function () {
  "use strict";

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function trunc(s, n) {
    s = String(s == null ? "" : s);
    return s.length > n ? s.slice(0, n - 1) + "\u2026" : s;
  }

  function JoMapView() {
    this.el = document.getElementById("map-view");
    this.titleEl = document.getElementById("map-title");
    this.summaryEl = document.getElementById("map-summary");
    this.filesEl = document.getElementById("map-files");
    this.endpointsEl = document.getElementById("map-endpoints");
    this.screensEl = document.getElementById("map-screens");
    this.connectionsEl = document.getElementById("map-connections");
    this.searchInput = document.getElementById("map-search");
    this.nodes = [];
    this.edges = [];
    this.current = null;
    this.projectSummary = "";
    this.recentWork = [];
    this.recentMode = false;
    this.sessionsOpen = false;
    this.fileToNode = new Map();
  }

  JoMapView.prototype.nodeById = function (id) {
    for (let i = 0; i < this.nodes.length; i++) {
      if (this.nodes[i].id === id) return this.nodes[i];
    }
    return null;
  };
  JoMapView.prototype.childrenOf = function (id) {
    return this.nodes.filter((n) => n.parent === id);
  };
  JoMapView.prototype.edgesTouching = function (id) {
    return this.edges.filter((e) => e.from === id || e.to === id);
  };

  JoMapView.prototype.load = async function (base) {
    const urls = [];
    if (base) urls.push(base + "/v1/floorplan");
    urls.push("../floorplan/graph.json");
    urls.push("floorplan/graph.json");
    for (const u of urls) {
      let data = null;
      try {
        const res = await fetch(u, { cache: "no-store" });
        if (res.ok) data = await res.json();
      } catch (err) {
        data = null;
      }
      if (data) {
        const graph = (data && data.graph) || data || {};
        this.nodes = Array.isArray(graph.nodes) ? graph.nodes : [];
        this.edges = Array.isArray(graph.edges) ? graph.edges : (Array.isArray(data && data.edges) ? data.edges : []);
        this.setRecentWork(data);
        this.buildFileToNode();
        this.projectSummary =
          (data && data.summary) ||
          ((data && data.architecture && data.architecture.project && data.architecture.project.summary) || "") ||
          ((graph.project && graph.project.summary) || "") ||
          "";
        this.renderBoard();
        if (!data.recentWork) this.fetchRecentWorkFallback();
        return;
      }
    }
    this.nodes = [];
    this.edges = [];
    this.projectSummary =
      "The Floorplan map is unavailable right now — connect the backend to see the whole picture.";
    this.renderBoard();
  };

  function matchesName(n, q) {
    const text = String(q || "").trim().toLowerCase();
    if (!text) return true;
    return (n.id + " " + (n.label || "") + " " + (n.summary || "")).toLowerCase().includes(text);
  }

  JoMapView.prototype.renderBoard = function () {
    this.current = null;
    if (this.el) this.el.innerHTML = "";
    const q = this.searchInput ? this.searchInput.value : "";
    const tops = this.nodes.filter((n) => !n.parent && matchesName(n, q));
    for (const n of tops) this.el.appendChild(this.card(n));
    this.markRecent();
    this.setupZoom();
    this.clearDetail();
  };

  JoMapView.prototype.card = function (n) {
    const el = document.createElement("div");
    el.className = "map-card";
    el.setAttribute("role", "button");
    el.setAttribute("tabindex", "0");
    el.dataset.id = n.id;
    el.title = n.summary || n.id;
    const head = document.createElement("div");
    head.className = "map-card-head";
    const label = document.createElement("span");
    label.className = "map-card-label";
    label.textContent = n.label || n.id;
    const kind = document.createElement("span");
    kind.className = "map-card-kind";
    kind.textContent = (n.kind || "").toUpperCase();
    const filesN = document.createElement("span");
    filesN.className = "map-card-files";
    filesN.textContent = (n.files || []).length + " files";
    head.appendChild(label);
    head.appendChild(kind);
    head.appendChild(filesN);
    const summary = document.createElement("div");
    summary.className = "map-card-summary";
    summary.textContent = trunc(n.summary || "", 120);
    const foot = document.createElement("div");
    foot.className = "map-card-foot";
    const kids = this.childrenOf(n.id).map((c) => c.label).join(", ");
    foot.textContent = n.id + (kids ? " · " + kids : "");
    el.appendChild(head);
    el.appendChild(summary);
    el.appendChild(foot);
    el.addEventListener("click", () => this.openDetail(n.id));
    return el;
  };

  JoMapView.prototype.openDetail = function (id) {
    this.current = id;
    const n = this.nodeById(id);
    if (!n) {
      this.clearDetail();
      return;
    }
    this.titleEl.textContent = n.label || n.id;
    this.summaryEl.textContent = n.summary || this.projectSummary;
    const files = n.files || [];
    this.filesEl.innerHTML = files
      .map(
        (f) =>
          '<div class="map-file"><span class="map-file-path">' +
          esc(f.path) +
          "</span>" +
          (f.description
            ? '<span class="map-file-desc">' + esc(trunc(f.description, 110)) + "</span>"
            : "") +
          "</div>",
      )
      .join("");
    if (!files.length) this.filesEl.innerHTML = '<div class="map-note">(no files assigned)</div>';
    const eps = n.endpoints || [];
    this.endpointsEl.innerHTML = eps
      .map((e) => '<div class="map-ep">' + esc(e.method) + " " + esc(e.path) + "</div>")
      .join("");
    if (!eps.length) this.endpointsEl.innerHTML = '<div class="map-note">(none — see parent part)</div>';
    const screens = n.screens || [];
    this.screensEl.innerHTML = screens.map((s) => '<div class="map-screen">' + esc(s) + "</div>").join("");
    if (!screens.length) this.screensEl.innerHTML = '<div class="map-note">(no separate screens)</div>';
    const conns = this.edgesTouching(id);
    this.connectionsEl.innerHTML = conns
      .map((e) => {
        const other = e.to === id ? e.from : e.to;
        const linkable = !!this.nodeById(other);
        const cls = "map-conn" + (linkable ? " map-conn-link" : "");
        return (
          '<div class="' + cls + '" data-node="' + esc(other) + '">' +
          '<span class="map-conn-from">' + esc(e.from) + " → " + esc(e.to) + "</span>" +
          '<span class="map-conn-label">' + esc(e.label) + "</span>" +
          (e.description
            ? '<span class="map-conn-desc">' + esc(trunc(e.description, 90)) + "</span>"
            : "") +
          "</div>"
        );
      })
      .join("");
    if (!conns.length) this.connectionsEl.innerHTML = '<div class="map-note">(no explicit connections)</div>';
    this.connectionsEl.querySelectorAll(".map-conn-link").forEach((el) => {
      el.addEventListener("click", () => this.openDetail(el.dataset.node));
    });
  };

  JoMapView.prototype.setRecentWork = function (data) {
    const rw = (data && data.recentWork) || null;
    this.recentWork = rw && Array.isArray(rw.tasks) ? rw.tasks : [];
  };

  JoMapView.prototype.buildFileToNode = function () {
    this.fileToNode = new Map();
    for (const n of this.nodes) {
      if (!n.id) continue;
      this.fileToNode.set(n.id, n.id);
      for (const f of n.files || []) {
        if (f && f.path) this.fileToNode.set(f.path, n.id);
      }
    }
  };

  JoMapView.prototype.fetchRecentWorkFallback = function () {
    const self = this;
    fetch("floorplan/recent-work.json", { cache: "no-store" })
      .then((res) => (res.ok ? res.json() : null))
      .then((doc) => {
        if (doc && Array.isArray(doc.tasks)) {
          self.recentWork = doc.tasks;
          self.markRecent();
        }
      })
      .catch(() => {});
  };

  JoMapView.prototype.markRecent = function () {
    const recent = new Set();
    for (const t of this.recentWork) {
      for (const it of t.items || []) {
        if (it && it.ref) {
          recent.add(it.ref);
          const nodeId = this.fileToNode.get(it.ref);
          if (nodeId) recent.add(nodeId);
        }
      }
    }
    for (const el of this.el.querySelectorAll(".map-card")) {
      const node = this.nodeById(el.dataset.id);
      const isRecent =
        recent.has(el.dataset.id) ||
        (!!node && (recent.has(node.id) || (node.files || []).some((f) => recent.has(f.path))));
      el.classList.toggle("map-card--recent", isRecent);
    }
  };

  JoMapView.prototype.toggleRecent = function () {
    this.recentMode = !this.recentMode;
    const btn = document.getElementById("map-recent-toggle");
    if (btn) {
      btn.classList.toggle("map-recent-toggle--on", this.recentMode);
      btn.setAttribute("aria-pressed", String(this.recentMode));
    }
    if (this.recentMode) this.renderRecent();
    else {
      this.current = null;
      this.clearDetail();
      this.renderBoard();
    }
  };

  JoMapView.prototype.renderRecent = function () {
    this.el.innerHTML = "";
    if (!this.recentWork.length) {
      this.el.innerHTML = '<div class="map-note">No recent work recorded yet.</div>';
      return;
    }
    for (const t of this.recentWork) this.el.appendChild(this.recentTaskEl(t));
  };

  JoMapView.prototype.recentTaskEl = function (t) {
    const el = document.createElement("div");
    el.className = "recent-task";
    const head = document.createElement("div");
    head.className = "recent-task-head";
    const title = document.createElement("span");
    title.className = "recent-task-title";
    title.textContent = t.title || "Work";
    const when = document.createElement("span");
    when.className = "recent-task-when";
    when.textContent = (t.updatedAt || "").slice(0, 10);
    head.appendChild(title);
    head.appendChild(when);
    const summary = document.createElement("div");
    summary.className = "recent-task-summary";
    summary.textContent = trunc(t.summary || t.request || "", 130);
    const items = document.createElement("ul");
    items.className = "recent-task-items";
    for (const it of t.items || []) {
      const li = document.createElement("li");
      li.className = "recent-item recent-item-" + (it.change === "new" ? "new" : "changed");
      const ref = document.createElement("span");
      ref.className = "recent-item-ref";
      ref.textContent = it.ref;
      const note = document.createElement("span");
      note.className = "recent-item-note";
      note.textContent = trunc(it.note || "", 90);
      li.appendChild(ref);
      li.appendChild(note);
      items.appendChild(li);
    }
    el.appendChild(head);
    el.appendChild(summary);
    el.appendChild(items);
    el.addEventListener("click", () => {
      // Clicking recent work returns to the map with the changed parts highlighted.
      this.recentMode = false;
      const btn = document.getElementById("map-recent-toggle");
      if (btn) {
        btn.classList.remove("map-recent-toggle--on");
        btn.setAttribute("aria-pressed", "false");
      }
      this.current = null;
      this.clearDetail();
      this.renderBoard();
    });
    return el;
  };

  JoMapView.prototype.setSessions = function (provider, onSelect) {
    this.sessionsProvider = provider;
    this.sessionOnSelect = onSelect;
  };

  JoMapView.prototype.toggleSessions = function () {
    const list = document.getElementById("map-sessions");
    if (!list) return;
    this.sessionsOpen = !this.sessionsOpen;
    list.hidden = !this.sessionsOpen;
    const btn = document.getElementById("map-sessions-toggle");
    if (btn) {
      btn.classList.toggle("map-recent-toggle--on", this.sessionsOpen);
      btn.setAttribute("aria-pressed", String(this.sessionsOpen));
    }
    if (this.sessionsOpen) this.renderSessions();
  };

  JoMapView.prototype.renderSessions = function () {
    const list = document.getElementById("map-sessions-list");
    if (!list) return;
    let data = { sessions: [], currentId: null };
    try {
      const p = this.sessionsProvider && this.sessionsProvider();
      if (p) data = p;
    } catch (err) {}
    const items = data.sessions || [];
    if (!items.length) {
      list.innerHTML = '<div class="map-note">(none yet)</div>';
      return;
    }
    const currentId = data.currentId;
    list.innerHTML = "";
    for (const s of items) {
      const el = document.createElement("div");
      el.className = "map-session-item" + (s && s.id === currentId ? " active" : "");
      const title = document.createElement("span");
      title.className = "map-session-title";
      title.textContent = (s && (s.title || "New chat")) || "New chat";
      el.appendChild(title);
      const id = s && s.id;
      el.addEventListener("click", () => {
        if (this.sessionOnSelect && id) this.sessionOnSelect(id);
      });
      list.appendChild(el);
    }
  };

  JoMapView.prototype.setupZoom = function () {
    if (this.zoomSet) return;
    this.zoomSet = true;
    const el = this.el;
    if (!el) return;
    el.style.transformOrigin = "0 0";
    this.zoom = 1;
    this.panX = 0;
    this.panY = 0;
    let dragging = false;
    el.addEventListener(
      "wheel",
      (e) => {
        e.preventDefault();
        const f = e.deltaY < 0 ? 1.12 : 0.89;
        this.zoom = Math.max(0.25, Math.min(4, this.zoom * f));
        this.applyZoom();
      },
      { passive: false },
    );
    el.addEventListener("mousedown", (e) => {
      dragging = true;
      this.dragX = e.clientX;
      this.dragY = e.clientY;
      e.preventDefault();
    });
    document.addEventListener("mousemove", (e) => {
      if (!dragging) return;
      this.panX += e.clientX - this.dragX;
      this.panY += e.clientY - this.dragY;
      this.dragX = e.clientX;
      this.dragY = e.clientY;
      this.applyZoom();
    });
    document.addEventListener("mouseup", () => {
      dragging = false;
    });
    el.addEventListener("dblclick", () => {
      this.zoom = 1;
      this.panX = 0;
      this.panY = 0;
      this.applyZoom();
    });
  };

  JoMapView.prototype.applyZoom = function () {
    if (this.el) this.el.style.transform = "translate(" + this.panX + "px, " + this.panY + "px) scale(" + this.zoom + ")";
  };

  JoMapView.prototype.clearDetail = function () {
    this.current = null;
    if (this.titleEl) this.titleEl.textContent = "";
    if (this.summaryEl) this.summaryEl.textContent = this.projectSummary;
    [this.filesEl, this.endpointsEl, this.screensEl, this.connectionsEl].forEach((el) => {
      if (el) el.innerHTML = "";
    });
  };

  window.JoMapView = JoMapView;
})();
