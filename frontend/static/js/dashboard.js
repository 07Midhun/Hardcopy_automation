// Dashboard JS: loads metrics and initializes Chart.js
let docTypeChartInstance = null;
let statusChartInstance = null;

document.addEventListener("DOMContentLoaded", () => {
  loadDashboardStats();
  // Poll every 15 seconds
  setInterval(loadDashboardStats, 15000);
});

async function loadDashboardStats() {
  try {
    const res = await fetch("/api/dashboard/stats");
    if (!res.ok) return;
    const data = await res.json();

    // Update KPIs
    document.getElementById("kpi-total").innerText = data.kpis.total_documents.toLocaleString();
    document.getElementById("kpi-completed").innerText = data.kpis.completed.toLocaleString();
    document.getElementById("kpi-review").innerText = data.kpis.review_required.toLocaleString();
    document.getElementById("kpi-failed").innerText = data.kpis.failed.toLocaleString();
    document.getElementById("kpi-pending").innerText = data.kpis.pending.toLocaleString();
    document.getElementById("kpi-confidence").innerText = Math.round(data.kpis.average_confidence * 100) + "%";

    // Update Charts
    updateDocTypeChart(data.doc_type_distribution);
    updateStatusChart(data.status_distribution);

    // Update Tables
    renderRecentJobs(data.recent_jobs);
    renderReviewQueue(data.review_queue_preview);
  } catch (err) {
    console.error("Failed to load dashboard statistics:", err);
  }
}

function updateDocTypeChart(dist) {
  const ctx = document.getElementById("docTypeChart");
  if (!ctx) return;

  const labels = Object.keys(dist).length > 0 ? Object.keys(dist) : ["No Documents Yet"];
  const values = Object.keys(dist).length > 0 ? Object.values(dist) : [1];
  const colors = ["#1e3a8a", "#0284c7", "#059669", "#d97706", "#7c3aed", "#94a3b8"];

  if (docTypeChartInstance) {
    docTypeChartInstance.data.labels = labels;
    docTypeChartInstance.data.datasets[0].data = values;
    docTypeChartInstance.update();
  } else {
    docTypeChartInstance = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [{
          data: values,
          backgroundColor: colors.slice(0, labels.length)
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { position: "bottom" }
        }
      }
    });
  }
}

function updateStatusChart(dist) {
  const ctx = document.getElementById("statusChart");
  if (!ctx) return;

  const labels = ["Completed", "Review Required", "Failed", "Pending"];
  const values = [
    dist.completed || 0,
    dist.review_required || 0,
    dist.failed || 0,
    dist.pending || 0
  ];

  if (statusChartInstance) {
    statusChartInstance.data.datasets[0].data = values;
    statusChartInstance.update();
  } else {
    statusChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [{
          label: "Documents",
          data: values,
          backgroundColor: ["#059669", "#d97706", "#dc2626", "#0284c7"]
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } }
        }
      }
    });
  }
}

function renderRecentJobs(jobs) {
  const tbody = document.getElementById("recent-jobs-table");
  if (!tbody) return;

  if (!jobs || jobs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-muted py-4">No batch jobs executed yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = jobs.map(job => `
    <tr>
      <td>
        <span class="fw-bold text-dark">${job.id}</span>
        <div class="text-muted small">${job.batch_name || 'Standard Batch'}</div>
      </td>
      <td><span class="badge bg-light text-dark border">${job.total_documents} docs</span></td>
      <td><span class="badge-status ${job.status}">${job.status.replace('_', ' ')}</span></td>
      <td style="width: 130px;">
        <div class="d-flex align-items-center gap-2">
          <div class="progress flex-grow-1" style="height: 6px;">
            <div class="progress-bar bg-primary" role="progressbar" style="width: ${job.progress_percentage}%;"></div>
          </div>
          <span class="small text-muted">${job.progress_percentage}%</span>
        </div>
      </td>
    </tr>
  `).join("");
}

function renderReviewQueue(docs) {
  const tbody = document.getElementById("review-queue-table");
  if (!tbody) return;

  if (!docs || docs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-center text-success py-4"><i class="fa-solid fa-circle-check me-2"></i>No documents requiring review!</td></tr>`;
    return;
  }

  tbody.innerHTML = docs.map(doc => `
    <tr>
      <td><span class="font-monospace fw-semibold">${doc.id}</span></td>
      <td><span class="text-truncate d-inline-block" style="max-width: 140px;" title="${doc.original_filename}">${doc.original_filename}</span></td>
      <td><span class="badge bg-light text-dark border">${doc.document_type}</span></td>
      <td>
        <a href="/review/${doc.id}" class="btn btn-sm btn-outline-warning">
          <i class="fa-solid fa-pen-to-square me-1"></i> Review
        </a>
      </td>
    </tr>
  `).join("");
}

