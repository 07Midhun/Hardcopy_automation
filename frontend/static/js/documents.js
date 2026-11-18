// Document Manager script
let currentPage = 1;
let searchDebounceTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  loadDocuments(1);
});

function handleSearch(e) {
  clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(() => {
    loadDocuments(1);
  }, 350);
}

function resetFilters() {
  document.getElementById("filterSearch").value = "";
  document.getElementById("filterStatus").value = "";
  document.getElementById("filterDocType").value = "";
  loadDocuments(1);
}

async function loadDocuments(page = 1) {
  currentPage = page;
  const status = document.getElementById("filterStatus").value;
  const docType = document.getElementById("filterDocType").value;
  const search = document.getElementById("filterSearch").value.trim();

  let url = `/api/documents?page=${page}&per_page=20`;
  if (status) url += `&status=${encodeURIComponent(status)}`;
  if (docType) url += `&document_type=${encodeURIComponent(docType)}`;
  if (search) url += `&search=${encodeURIComponent(search)}`;

  try {
    const res = await fetch(url);
    if (!res.ok) return;
    const data = await res.json();

    document.getElementById("docCountBadge").innerText = `${data.total.toLocaleString()} Total`;
    document.getElementById("paginationInfo").innerText = `Showing page ${data.page} of ${Math.max(1, data.pages)} (${data.total.toLocaleString()} documents)`;

    renderDocumentsTable(data.documents);
    renderPagination(data.page, data.pages);
  } catch (err) {
    console.error("Error loading documents:", err);
  }
}

function renderDocumentsTable(docs) {
  const tbody = document.getElementById("documentsTableBody");
  if (!docs || docs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-center text-muted py-5">No documents match the current criteria.</td></tr>`;
    return;
  }

  tbody.innerHTML = docs.map(doc => {
    const confPct = Math.round((doc.confidence_average || 0) * 100);
    let confBadgeClass = "bg-success";
    if (confPct < 60) confBadgeClass = "bg-danger";
    else if (confPct < 85) confBadgeClass = "bg-warning text-dark";

    const uploadDate = doc.uploaded_at ? new Date(doc.uploaded_at).toLocaleString() : 'N/A';

    return `
      <tr>
        <td>
          <a href="/documents/${doc.id}" class="font-monospace fw-bold text-primary text-decoration-none">
            ${doc.id}
          </a>
        </td>
        <td>
          <span class="fw-medium text-dark d-inline-block text-truncate" style="max-width: 200px;" title="${doc.original_filename}">
            ${doc.original_filename}
          </span>
          <div class="text-muted small">${(doc.file_size / 1024).toFixed(1)} KB</div>
        </td>
        <td>
          <span class="badge bg-light text-dark border">${doc.document_type}</span>
        </td>
        <td>
          <span class="badge-status ${doc.status}">${doc.status.replace('_', ' ')}</span>
          ${doc.error_message ? `<div class="text-danger small text-truncate" style="max-width: 150px;" title="${doc.error_message}">${doc.error_message}</div>` : ''}
        </td>
        <td>
          <span class="badge ${confBadgeClass}">${confPct}%</span>
        </td>
        <td class="small text-muted">${uploadDate}</td>
        <td class="text-end">
          <div class="btn-group btn-group-sm">
            <a href="/documents/${doc.id}" class="btn btn-outline-secondary" title="Inspect Extraction">
              <i class="fa-solid fa-eye"></i>
            </a>
            <a href="/review/${doc.id}" class="btn btn-outline-warning" title="Review & Verify">
              <i class="fa-solid fa-pen-to-square"></i>
            </a>
            <button class="btn btn-outline-danger" onclick="retryDocument('${doc.id}')" title="Retry Extraction">
              <i class="fa-solid fa-rotate-right"></i>
            </button>
          </div>
        </td>
      </tr>
    `;
  }).join("");
}

function renderPagination(current, totalPages) {
  const container = document.getElementById("paginationControls");
  if (!container || totalPages <= 1) {
    container.innerHTML = "";
    return;
  }

  let html = "";
  html += `<li class="page-item ${current === 1 ? 'disabled' : ''}"><button class="page-link" onclick="loadDocuments(${current - 1})">Previous</button></li>`;

  const start = Math.max(1, current - 2);
  const end = Math.min(totalPages, current + 2);

  for (let i = start; i <= end; i++) {
    html += `<li class="page-item ${i === current ? 'active' : ''}"><button class="page-link" onclick="loadDocuments(${i})">${i}</button></li>`;
  }

  html += `<li class="page-item ${current === totalPages ? 'disabled' : ''}"><button class="page-link" onclick="loadDocuments(${current + 1})">Next</button></li>`;
  container.innerHTML = html;
}

async function retryDocument(docId) {
  if (!confirm(`Retry AI extraction on document ${docId}?`)) return;
  try {
    const res = await fetch(`/api/documents/${docId}/retry`, { method: "POST" });
    if (res.ok) {
      alert(`Retry dispatched for ${docId}!`);
      loadDocuments(currentPage);
    } else {
      alert("Failed to retry document.");
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

