const state = {
  owner: "Tutti",
  category: "Tutte",
  status: "Tutti",
  query: "",
  selectedId: null,
  documents: [
    {
      id: "rev-001",
      title: "POS_pagina_iniziale_con_nuova_firma.docx",
      category: "Lavoro",
      subcategory: "Sicurezza cantiere",
      owner: "Azienda/Lavoro",
      confidence: 98,
      status: "pending",
      action: "Verificare e completare la firma",
      source: "AnythingLLM / GPT mini",
      driveLink: "#",
      reason: "Documento operativo per sicurezza e controlli con data e firme da completare.",
    },
    {
      id: "rev-002",
      title: "Fornitura e posa in opera di cancello scorrevole Dim.docx",
      category: "Lavoro",
      subcategory: "Preventivo / Specifica tecnica",
      owner: "Azienda/Lavoro",
      confidence: 100,
      status: "approved",
      action: "Verificare specifiche tecniche e materiali",
      source: "AnythingLLM / GPT mini",
      driveLink: "#",
      reason: "Documento tecnico che descrive materiali e lavorazioni legate all'azienda.",
    },
    {
      id: "rev-003",
      title: "Scadenza Bolletta.ics",
      category: "Casa",
      subcategory: "Bolletta energia",
      owner: "Famiglia",
      confidence: 100,
      status: "approved",
      action: "Archivia",
      deadline: "24/04/2026",
      source: "Drive / calendario",
      driveLink: "#",
      reason: "Promemoria per pagamento bolletta Eni presso indirizzo familiare.",
    },
    {
      id: "rev-004",
      title: "Garanzia Onofri & C.doc",
      category: "Garanzie",
      subcategory: "Fideiussione affitto",
      owner: "Famiglia",
      confidence: 100,
      status: "approved",
      action: "Archivia",
      source: "AnythingLLM / GPT mini",
      driveLink: "#",
      reason: "Atto di fideiussione in cui familiari si costituiscono garanti per un contratto.",
    },
    {
      id: "rev-005",
      title: "piano_pasti_settimanale.docx",
      category: "Alimentazione",
      subcategory: "Piano nutrizionale",
      owner: "Davide",
      confidence: 100,
      status: "applied",
      action: "Archivia",
      source: "Drive",
      driveLink: "#",
      reason: "Piano alimentare dettagliato intestato a Davide Onofri.",
    },
    {
      id: "rev-006",
      title: "MODULO-AUTOCERTIFICAZIONE-ASSENZA-CONDANNE-PENALI 2.doc",
      category: "Lavoro",
      subcategory: "Modulo autocertificazione",
      owner: "Non chiaro",
      confidence: 90,
      status: "pending",
      action: "Da verificare",
      source: "AnythingLLM / GPT mini",
      driveLink: "#",
      reason: "Modulo in bianco spesso usato in contesti lavorativi; proprietario non chiaro.",
    },
    {
      id: "rev-007",
      title: "index.html",
      category: "Varie",
      subcategory: "File tecnico",
      owner: "Non chiaro",
      confidence: 50,
      status: "rejected",
      action: "Ignora",
      source: "Drive",
      driveLink: "#",
      reason: "File tecnico residuale con contenuto minimo, non utile per archivio documentale.",
    },
  ],
  pipeline: [
    { label: "Inventario Drive", detail: "500 file mappati", done: true },
    { label: "Download locale", detail: "200 file scaricati", done: true },
    { label: "Estrazione testo", detail: "42 testi leggibili", done: true },
    { label: "Classificazione AI", detail: "Review importate in SQLite", done: true },
    { label: "Conferma utente", detail: "Approva / rifiuta dalla UI", done: false },
    { label: "Spostamento Drive", detail: "Solo dopo approvazione", done: false },
  ],
};

const categoryNames = [
  "Banca",
  "Salute",
  "Assicurazioni",
  "Casa",
  "Auto",
  "Fisco",
  "Garanzie",
  "Sport",
  "Tecnologia",
  "Viaggi",
  "Lavoro",
  "Alimentazione",
  "Varie",
];

const statusLabels = {
  pending: "Pending",
  approved: "Approvato",
  rejected: "Rifiutato",
  applied: "Applicato",
};

function filteredDocuments() {
  const query = state.query.trim().toLowerCase();
  return state.documents.filter((doc) => {
    const matchesOwner = state.owner === "Tutti" || doc.owner === state.owner;
    const matchesCategory = state.category === "Tutte" || doc.category === state.category;
    const matchesStatus = state.status === "Tutti" || doc.status === state.status;
    const haystack = [doc.title, doc.category, doc.subcategory, doc.owner, doc.action, doc.reason].join(" ").toLowerCase();
    const matchesQuery = !query || haystack.includes(query);
    return matchesOwner && matchesCategory && matchesStatus && matchesQuery;
  });
}

function renderStats() {
  const docs = state.documents;
  document.getElementById("statInbox").textContent = "500";
  document.getElementById("statExtracted").textContent = "42";
  document.getElementById("statOcr").textContent = "158";
  document.getElementById("statReviews").textContent = docs.length.toString();
}

function renderCategoryFilter() {
  const select = document.getElementById("categoryFilter");
  select.innerHTML = '<option value="Tutte">Tutte le categorie</option>';
  categoryNames.forEach((category) => {
    const option = document.createElement("option");
    option.value = category;
    option.textContent = category;
    select.appendChild(option);
  });
  select.value = state.category;
}

function renderDocuments() {
  const table = document.getElementById("documentsTable");
  const docs = filteredDocuments();
  table.innerHTML = "";

  if (!docs.length) {
    table.appendChild(document.getElementById("emptyStateTemplate").content.cloneNode(true));
    return;
  }

  docs.forEach((doc) => {
    const row = document.createElement("tr");
    row.dataset.id = doc.id;
    row.innerHTML = `
      <td>
        <div class="doc-title">${escapeHtml(doc.title)}</div>
        <div class="doc-subtitle">${escapeHtml(doc.subcategory)} · ${escapeHtml(doc.source)}</div>
      </td>
      <td>${escapeHtml(doc.category)}</td>
      <td>${escapeHtml(doc.owner)}</td>
      <td>${doc.confidence}%</td>
      <td><span class="badge ${doc.status}">${statusLabels[doc.status]}</span></td>
      <td>
        <div class="action-buttons">
          <button class="small-button approve" data-action="approve" data-id="${doc.id}">Approva</button>
          <button class="small-button reject" data-action="reject" data-id="${doc.id}">Rifiuta</button>
        </div>
      </td>
    `;
    row.addEventListener("click", (event) => {
      if (event.target instanceof HTMLButtonElement) return;
      state.selectedId = doc.id;
      renderDetail();
    });
    table.appendChild(row);
  });
}

function renderCategories() {
  const grid = document.getElementById("categoryGrid");
  grid.innerHTML = "";
  categoryNames.forEach((category) => {
    const count = state.documents.filter((doc) => doc.category === category).length;
    if (!count && !["Lavoro", "Casa", "Garanzie", "Alimentazione", "Varie"].includes(category)) return;
    const card = document.createElement("div");
    card.className = "category-card";
    card.innerHTML = `<strong>${category}</strong><span>${count} documenti review</span>`;
    card.addEventListener("click", () => {
      state.category = category;
      document.getElementById("categoryFilter").value = category;
      render();
    });
    grid.appendChild(card);
  });
}

function renderDeadlines() {
  const list = document.getElementById("deadlineList");
  const deadlines = state.documents.filter((doc) => doc.deadline);
  list.innerHTML = "";
  if (!deadlines.length) {
    list.innerHTML = '<div class="deadline-item">Nessuna scadenza rilevata<span>Importa altre review AI</span></div>';
    return;
  }
  deadlines.forEach((doc) => {
    const item = document.createElement("div");
    item.className = "deadline-item";
    item.innerHTML = `<strong>${escapeHtml(doc.title)}</strong><span>${escapeHtml(doc.deadline)} · ${escapeHtml(doc.category)}</span>`;
    list.appendChild(item);
  });
}

function renderPipeline() {
  const timeline = document.getElementById("pipelineTimeline");
  timeline.innerHTML = "";
  state.pipeline.forEach((step) => {
    const item = document.createElement("div");
    item.className = "timeline-step";
    item.innerHTML = `
      <span class="timeline-dot ${step.done ? "done" : "todo"}"></span>
      <div>
        <strong>${escapeHtml(step.label)}</strong>
        <div class="doc-subtitle">${escapeHtml(step.detail)}</div>
      </div>
    `;
    timeline.appendChild(item);
  });
}

function renderDetail() {
  const doc = state.documents.find((item) => item.id === state.selectedId) || filteredDocuments()[0];
  const title = document.getElementById("detailTitle");
  const body = document.getElementById("detailBody");
  const meta = document.getElementById("detailMeta");
  if (!doc) {
    title.textContent = "Seleziona un documento";
    body.textContent = "Clicca una riga per vedere motivo AI, azione consigliata e link Drive.";
    meta.innerHTML = "";
    return;
  }
  title.textContent = doc.title;
  body.textContent = doc.reason;
  meta.innerHTML = `
    <div><strong>Categoria:</strong> ${escapeHtml(doc.category)} / ${escapeHtml(doc.subcategory)}</div>
    <div><strong>Proprietario:</strong> ${escapeHtml(doc.owner)}</div>
    <div><strong>Azione:</strong> ${escapeHtml(doc.action)}</div>
    <div><strong>Confidenza:</strong> ${doc.confidence}%</div>
  `;
}

function render() {
  renderStats();
  renderCategoryFilter();
  renderDocuments();
  renderCategories();
  renderDeadlines();
  renderPipeline();
  renderDetail();
}

function approveDocument(id) {
  const doc = state.documents.find((item) => item.id === id);
  if (!doc) return;
  doc.status = "approved";
  state.selectedId = id;
  render();
}

function rejectDocument(id) {
  const doc = state.documents.find((item) => item.id === id);
  if (!doc) return;
  doc.status = "rejected";
  state.selectedId = id;
  render();
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.dataset.action === "approve") approveDocument(target.dataset.id);
  if (target.dataset.action === "reject") rejectDocument(target.dataset.id);
});

document.querySelectorAll(".owner-button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".owner-button").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.owner = button.dataset.owner;
    render();
  });
});

document.getElementById("categoryFilter").addEventListener("change", (event) => {
  state.category = event.target.value;
  render();
});

document.getElementById("statusFilter").addEventListener("change", (event) => {
  state.status = event.target.value;
  render();
});

document.getElementById("searchInput").addEventListener("input", (event) => {
  state.query = event.target.value;
  render();
});

document.getElementById("clearSearch").addEventListener("click", () => {
  state.query = "";
  document.getElementById("searchInput").value = "";
  render();
});

document.getElementById("refreshButton").addEventListener("click", () => {
  render();
});

render();
