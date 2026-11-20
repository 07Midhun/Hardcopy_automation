// Bulk Upload & ZIP upload handlers with drag-and-drop and progress tracking
let selectedPdfFiles = [];
let selectedZipFile = null;

document.addEventListener("DOMContentLoaded", () => {
  setupPdfDropzone();
  setupZipDropzone();
});

function setupPdfDropzone() {
  const dropzone = document.getElementById("pdfDropzone");
  const fileInput = document.getElementById("pdfFileInput");

  if (!dropzone || !fileInput) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", e => {
    const files = Array.from(e.dataTransfer.files).filter(f => f.name.toLowerCase().endsWith(".pdf"));
    addPdfFiles(files);
  });

  fileInput.addEventListener("change", e => {
    const files = Array.from(e.target.files).filter(f => f.name.toLowerCase().endsWith(".pdf"));
    addPdfFiles(files);
  });
}

function addPdfFiles(newFiles) {
  selectedPdfFiles = selectedPdfFiles.concat(newFiles);
  updatePdfSelectionUI();
}

function clearSelectedFiles() {
  selectedPdfFiles = [];
  document.getElementById("pdfFileInput").value = "";
  updatePdfSelectionUI();
}

function updatePdfSelectionUI() {
  const count = selectedPdfFiles.length;
  const badge = document.getElementById("fileCountBadge");
  const info = document.getElementById("fileSelectionInfo");
  const btn = document.getElementById("btnStartPdfUpload");

  if (count > 0) {
    badge.innerText = `${count} PDF document${count > 1 ? 's' : ''}`;
    info.classList.remove("d-none");
    btn.disabled = false;
  } else {
    info.classList.add("d-none");
    btn.disabled = true;
  }
}

function submitPdfUpload() {
  if (selectedPdfFiles.length === 0) return;

  const batchName = document.getElementById("pdfBatchName").value.trim();
  const formData = new FormData();
  if (batchName) formData.append("batch_name", batchName);

  selectedPdfFiles.forEach(file => {
    formData.append("files", file);
  });

  const progressBar = document.getElementById("uploadProgressBar");
  const progressPercent = document.getElementById("uploadProgressPercent");
  const progressContainer = document.getElementById("uploadProgressBarContainer");
  const btn = document.getElementById("btnStartPdfUpload");

  progressContainer.classList.remove("d-none");
  btn.disabled = true;

  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/upload/bulk", true);

  xhr.upload.onprogress = e => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = pct + "%";
      progressPercent.innerText = pct + "%";
    }
  };

  xhr.onload = () => {
    if (xhr.status >= 200 && xhr.status < 300) {
      const res = JSON.parse(xhr.responseText);
      alert(`Success: Registered ${res.registered_count} documents for background extraction!`);
      window.location.href = res.job_id ? `/processing?job_id=${res.job_id}` : "/processing";
    } else {
      alert("Upload failed: " + xhr.responseText);
      btn.disabled = false;
    }
  };

  xhr.onerror = () => {
    alert("Network error during upload.");
    btn.disabled = false;
  };

  xhr.send(formData);
}

function setupZipDropzone() {
  const dropzone = document.getElementById("zipDropzone");
  const fileInput = document.getElementById("zipFileInput");
  if (!dropzone || !fileInput) return;

  ["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, e => {
      e.preventDefault();
      dropzone.classList.remove("dragover");
    });
  });

  dropzone.addEventListener("drop", e => {
    const file = Array.from(e.dataTransfer.files).find(f => f.name.toLowerCase().endsWith(".zip"));
    if (file) setZipFile(file);
  });

  fileInput.addEventListener("change", e => {
    if (e.target.files.length > 0) setZipFile(e.target.files[0]);
  });
}

function setZipFile(file) {
  selectedZipFile = file;
  document.getElementById("zipFileName").innerText = file.name;
  document.getElementById("zipFileSize").innerText = (file.size / (1024 * 1024)).toFixed(2) + " MB";
  document.getElementById("zipSelectionInfo").classList.remove("d-none");
  document.getElementById("btnStartZipUpload").disabled = false;
}

function submitZipUpload() {
  if (!selectedZipFile) return;

  const batchName = document.getElementById("zipBatchName").value.trim();
  const formData = new FormData();
  if (batchName) formData.append("batch_name", batchName);
  formData.append("file", selectedZipFile);

  const btn = document.getElementById("btnStartZipUpload");
  btn.disabled = true;
  btn.innerText = "Ingesting ZIP archive in background...";

  fetch("/api/upload/zip", {
    method: "POST",
    body: formData
  })
  .then(res => res.json())
  .then(data => {
    alert("ZIP archive submitted! Extraction queue activated.");
    window.location.href = "/processing";
  })
  .catch(err => {
    alert("Error uploading ZIP: " + err);
    btn.disabled = false;
    btn.innerText = "Upload ZIP & Dispatch Worker Ingestion";
  });
}

