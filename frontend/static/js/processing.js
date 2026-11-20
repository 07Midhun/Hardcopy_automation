// Processing monitor and job queue manager
let activeJobId = null;
let pollInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  refreshJobsList();
  pollInterval = setInterval(refreshJobsList, 5000);
});

async function refreshJobsList() {
  try {
    const res = await fetch("/api/jobs?per_page=20");
    if (!res.ok) return;
    const data = await res.json();
    renderJobsTable(data.jobs);

    // Pick target job: keep user selection, or URL job_id, or first active job with documents, or latest job
    if (data.jobs && data.jobs.length > 0) {
      let targetJob = null;
      if (activeJobId) {
        targetJob = data.jobs.find(j => j.id === activeJobId);
      }
      if (!targetJob) {
        const urlJobId = new URLSearchParams(window.location.search).get("job_id");
        if (urlJobId) {
          targetJob = data.jobs.find(j => j.id === urlJobId);
        }
      }
      if (!targetJob) {
        targetJob = data.jobs.find(j => ["processing", "queued", "pending"].includes(j.status) && j.total_documents > 0) || data.jobs[0];
      }
      if (targetJob) {
        activeJobId = targetJob.id;
        loadJobProgress(targetJob.id);
      }
    }
  } catch (err) {
    console.error("Error refreshing jobs list:", err);
  }
}

async function loadJobProgress(jobId) {
  try {
    const res = await fetch(`/api/jobs/${jobId}/progress`);
    if (!res.ok) return;
    const p = await res.json();

    document.getElementById("activeJobTitle").innerText = `Batch: ${jobId}`;
    document.getElementById("activeJobBadge").innerText = p.status.toUpperCase();
    document.getElementById("activeProgressText").innerText = `${p.progress_percentage}%`;
    document.getElementById("activeProgressBar").style.width = `${p.progress_percentage}%`;

    document.getElementById("metricTotal").innerText = p.total_documents;
    document.getElementById("metricCompleted").innerText = p.completed;
    document.getElementById("metricReview").innerText = p.review_required;
    document.getElementById("metricFailed").innerText = p.failed;
    document.getElementById("metricInProgress").innerText = p.in_progress;
    document.getElementById("metricQueued").innerText = p.queued;

    const retryBtn = document.getElementById("btnRetryActiveFailed");
    if (p.failed > 0) {
      retryBtn.style.display = "inline-block";
    } else {
      retryBtn.style.display = "none";
    }
  } catch (err) {
    console.error(`Failed to load progress for job ${jobId}:`, err);
  }
}

function renderJobsTable(jobs) {
  const tbody = document.getElementById("allJobsTableBody");
  if (!tbody) return;

  if (!jobs || jobs.length === 0) {
    tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted py-5">No jobs submitted yet.</td></tr>`;
    return;
  }

  tbody.innerHTML = jobs.map(job => `
    <tr>
      <td><span class="font-monospace fw-bold text-dark">${job.id}</span></td>
      <td><span class="fw-semibold">${job.batch_name || 'Standard Batch'}</span></td>
      <td><span class="badge bg-light text-dark border">${job.total_documents}</span></td>
      <td class="text-success fw-bold">${job.completed_documents}</td>
      <td class="text-warning fw-bold">${job.review_required_documents}</td>
      <td class="text-danger fw-bold">${job.failed_documents}</td>
      <td><span class="badge-status ${job.status}">${job.status.replace('_', ' ')}</span></td>
      <td style="width: 130px;">
        <div class="d-flex align-items-center gap-2">
          <div class="progress flex-grow-1" style="height: 6px;">
            <div class="progress-bar bg-primary" style="width: ${job.progress_percentage}%;"></div>
          </div>
          <span class="small text-muted">${job.progress_percentage}%</span>
        </div>
      </td>
      <td class="text-end">
        <div class="btn-group btn-group-sm">
          <button class="btn btn-outline-primary" onclick="selectActiveJob('${job.id}')" title="Inspect Progress">
            <i class="fa-solid fa-chart-line"></i>
          </button>
          <a href="/api/export/consolidated?job_id=${job.id}" class="btn btn-outline-success" target="_blank" title="Export Excel">
            <i class="fa-solid fa-file-excel"></i>
          </a>
          ${job.failed_documents > 0 ? `
            <button class="btn btn-outline-danger" onclick="retryFailedJob('${job.id}')" title="Retry Failed">
              <i class="fa-solid fa-rotate-right"></i>
            </button>
          ` : ''}
        </div>
      </td>
    </tr>
  `).join("");
}

function selectActiveJob(jobId) {
  activeJobId = jobId;
  loadJobProgress(jobId);
}

async function retryActiveJobFailed() {
  if (!activeJobId) return;
  await retryFailedJob(activeJobId);
}

async function retryFailedJob(jobId) {
  if (!confirm(`Retry all failed documents in batch ${jobId}?`)) return;
  try {
    const res = await fetch(`/api/jobs/${jobId}/retry-failed`, { method: "POST" });
    if (res.ok) {
      alert("Retrying failed documents in batch!");
      refreshJobsList();
    } else {
      alert("Failed to enqueue retry.");
    }
  } catch (err) {
    alert("Error: " + err);
  }
}

