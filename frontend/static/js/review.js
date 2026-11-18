// Side-by-Side Review Workstation JS
let currentDocId = null;
let currentZoom = 1.0;
let currentRotation = 0;
let loadedExtractionData = null;

document.addEventListener("DOMContentLoaded", () => {
  const initialDocId = document.getElementById("activeDocIdInput").value;
  loadReviewQueue(initialDocId);
});

async function loadReviewQueue(targetDocId = null) {
  try {
    const res = await fetch("/api/review/queue?per_page=50");
    if (!res.ok) return;
    const data = await res.json();
    const select = document.getElementById("reviewQueueSelect");

    select.innerHTML = '<option value="">-- Select document needing review --</option>';

    data.queue.forEach(doc => {
      const opt = document.createElement("option");
      opt.value = doc.id;
      opt.innerText = `${doc.id} - ${doc.original_filename} (${doc.document_type})`;
      select.appendChild(opt);
    });

    if (targetDocId) {
      select.value = targetDocId;
      loadDocumentForReview(targetDocId);
    } else if (data.queue.length > 0) {
      select.value = data.queue[0].id;
      loadDocumentForReview(data.queue[0].id);
    }
  } catch (err) {
    console.error("Error loading review queue:", err);
  }
}

function onSelectQueueDocument(docId) {
  if (docId) {
    loadDocumentForReview(docId);
  }
}

async function loadDocumentForReview(docId) {
  currentDocId = docId;
  resetZoom();

  // Load preview image in Left Panel
  const img = document.getElementById("reviewDocImage");
  const placeholder = document.getElementById("viewerPlaceholder");
  const filenameSpan = document.getElementById("viewerFilename");

  filenameSpan.innerText = `Loading ${docId}...`;
  img.src = `/api/documents/${docId}/preview`;
  img.onload = () => {
    img.classList.remove("d-none");
    placeholder.classList.add("d-none");
  };
  img.onerror = () => {
    img.classList.add("d-none");
    placeholder.classList.remove("d-none");
  };

  // Load extraction fields in Right Panel
  try {
    const res = await fetch(`/api/documents/${docId}/extraction`);
    if (!res.ok) return;
    const data = await res.json();
    loadedExtractionData = data;

    filenameSpan.innerText = `${data.source_filename} (${data.document_type})`;
    document.getElementById("fieldsHeaderTitle").innerText = `${data.document_type} - ${docId}`;
    document.getElementById("fieldsConfidenceBadge").innerText = `Avg: ${Math.round((data.confidence_average || 0) * 100)}%`;

    renderFields(data.records);
  } catch (err) {
    console.error("Error loading extraction data:", err);
  }
}

function renderFields(records) {
  const container = document.getElementById("fieldsContainer");
  if (!records || records.length === 0) {
    container.innerHTML = `
      <div class="text-center text-muted py-5">
        <i class="fa-solid fa-triangle-exclamation fa-3x mb-3 text-warning"></i>
        <h5>No fields extracted for this document</h5>
      </div>
    `;
    return;
  }

  let html = "";
  records.forEach((record, recIdx) => {
    html += `
      <div class="section-group">
        <div class="section-title">
          <span><i class="fa-solid fa-layer-group me-2"></i>${record.section}</span>
          <span class="badge bg-light text-secondary border">Record #${record.record_number}</span>
        </div>
    `;

    record.fields.forEach(field => {
      const confPct = Math.round((field.confidence_score || 0) * 100);
      let confClass = "conf-high";
      if (confPct < 60) confClass = "conf-low";
      else if (confPct < 85) confClass = "conf-medium";

      const originalVal = field.original_extracted_value || '';
      const currentVal = field.current_value !== null ? field.current_value : '';

      html += `
        <div class="field-row" data-field-id="${field.id}">
          <div class="d-flex justify-content-between align-items-center mb-1">
            <label class="form-label mb-0 fw-semibold text-secondary small">${field.field_name}</label>
            <div class="d-flex align-items-center gap-2">
              <span class="confidence-pill ${confClass}" title="AI Confidence Score">${confPct}%</span>
              <select class="form-select form-select-sm field-status-select" style="width: 140px;">
                <option value="verified" ${field.verification_status === 'verified' ? 'selected' : ''}>Verified</option>
                <option value="review_required" ${field.verification_status === 'review_required' ? 'selected' : ''}>Review Required</option>
                <option value="unreadable" ${field.verification_status === 'unreadable' ? 'selected' : ''}>Unreadable</option>
                <option value="missing" ${field.verification_status === 'missing' ? 'selected' : ''}>Missing</option>
              </select>
            </div>
          </div>
          <div class="input-group input-group-sm">
            <input type="text" class="form-control font-monospace field-value-input" value="${escapeHtml(currentVal)}">
          </div>
          <div class="field-meta d-flex justify-content-between">
            <span>Raw AI output: <code class="text-muted">${escapeHtml(originalVal) || '[None]'}</code></span>
            ${field.verification_status === 'review_required' ? '<span class="text-warning fw-bold"><i class="fa-solid fa-flag me-1"></i>Verify</span>' : ''}
          </div>
        </div>
      `;
    });

    html += `</div>`;
  });

  container.innerHTML = html;
}

// Viewer Zoom & Pan Controls
function zoomIn() {
  currentZoom = Math.min(3.0, currentZoom + 0.25);
  applyTransform();
}

function zoomOut() {
  currentZoom = Math.max(0.5, currentZoom - 0.25);
  applyTransform();
}

function resetZoom() {
  currentZoom = 1.0;
  currentRotation = 0;
  applyTransform();
}

function rotateImage() {
  currentRotation = (currentRotation + 90) % 360;
  applyTransform();
}

function applyTransform() {
  const img = document.getElementById("reviewDocImage");
  if (img) {
    img.style.transform = `scale(${currentZoom}) rotate(${currentRotation}deg)`;
  }
}

// Save corrections and audit log
async function saveAllCorrections() {
  if (!currentDocId) return;

  const fieldRows = document.querySelectorAll(".field-row");
  const corrections = [];

  fieldRows.forEach(row => {
    const fieldId = parseInt(row.getAttribute("data-field-id"));
    const inputVal = row.querySelector(".field-value-input").value;
    const statusVal = row.querySelector(".field-status-select").value;

    corrections.push({
      field_id: fieldId,
      corrected_value: inputVal,
      verification_status: statusVal
    });
  });

  const btn = document.getElementById("btnSaveCorrections");
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin me-1"></i> Saving...`;

  try {
    const res = await fetch(`/api/documents/${currentDocId}/corrections`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corrections: corrections, document_status: "completed" })
    });

    if (res.ok) {
      alert(`Corrections and audit trail saved for ${currentDocId}!`);
      // Reload review queue and advance to next
      loadReviewQueue();
    } else {
      const err = await res.json();
      alert("Error saving: " + (err.error || "Unknown"));
    }
  } catch (err) {
    alert("Network error: " + err);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="fa-solid fa-floppy-disk me-1"></i> Save & Verify Document`;
  }
}

function escapeHtml(text) {
  if (!text) return "";
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

