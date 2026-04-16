/**
 * script.js — Secure File Sharing Dashboard
 * Token-based auth: token stored in localStorage, sent as Bearer header.
 */

const API = "http://127.0.0.1:5000";

// ── Auth helpers ──────────────────────────────────────────────────────────────
function getToken() {
  return localStorage.getItem("token");
}

function authHeaders() {
  return {
    "Authorization": "Bearer " + getToken()
  };
}

function authHeadersJSON() {
  return {
    "Authorization": "Bearer " + getToken(),
    "Content-Type": "application/json"
  };
}

// ── Auth guard on page load ───────────────────────────────────────────────────
(async () => {
  const token = getToken();
  if (!token) {
    window.location.href = "login.html";
    return;
  }
  const res  = await fetch(`${API}/auth/me`, { headers: authHeaders() });
  const data = await res.json();
  if (!data.success) {
    localStorage.clear();
    window.location.href = "login.html";
  } else {
    document.getElementById("navUser").textContent = `👤 ${data.username}`;
  }
})();

// ── Logout ────────────────────────────────────────────────────────────────────
async function logout() {
  await fetch(`${API}/auth/logout`, { method: "POST", headers: authHeaders() });
  localStorage.clear();
  window.location.href = "login.html";
}

// ── Tab switching ─────────────────────────────────────────────────────────────
function switchTab(name, btn) {
  document.querySelectorAll(".tab-content").forEach(s => s.classList.remove("active"));
  document.querySelectorAll(".tab").forEach(b => b.classList.remove("active"));
  document.getElementById("tab-" + name).classList.add("active");
  btn.classList.add("active");
  if (name === "files" || name === "shared") loadFiles();
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function setMsg(id, text, ok) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = text;
  el.className   = "msg " + (ok ? "success" : "error");
}

function formatBytes(bytes) {
  if (bytes < 1024)         return bytes + " B";
  if (bytes < 1024 * 1024)  return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(2) + " MB";
}

// ── Upload ────────────────────────────────────────────────────────────────────
function handleDrop(e) {
  e.preventDefault();
  document.getElementById("uploadInput").files = e.dataTransfer.files;
  previewFile();
}

function previewFile() {
  const input = document.getElementById("uploadInput");
  const file  = input.files[0];
  if (!file) return;
  document.getElementById("previewName").textContent = file.name;
  document.getElementById("previewSize").textContent = formatBytes(file.size);
  document.getElementById("filePreview").style.display = "flex";
}

async function doUpload() {
  const input = document.getElementById("uploadInput");
  const info  = document.getElementById("uploadInfo");
  info.style.display = "none";

  if (!input.files.length)
    return setMsg("uploadMsg", "❌ Please select a file first.", false);

  const formData = new FormData();
  formData.append("file", input.files[0]);

  setMsg("uploadMsg", "⏳ Encrypting and uploading …", true);

  try {
    const res  = await fetch(`${API}/files/upload`, {
      method: "POST",
      headers: authHeaders(),   // token auth — no Content-Type (browser sets multipart)
      body: formData
    });
    const data = await res.json();

    if (data.success) {
      setMsg("uploadMsg", "✅ " + data.message, true);
      info.style.display = "block";
      info.innerHTML =
        `<strong>File Hash (SHA-256):</strong><br>
         <code>${data.file_hash}</code><br><br>
         <strong>Blockchain TX:</strong><br>
         <code>${data.tx_hash}</code><br>
         <span class="badge ${data.blockchain ? "badge-green" : "badge-yellow"}">
           ${data.blockchain ? "🔗 Stored on-chain" : "⚠️ Ganache offline — hash saved to DB only"}
         </span>`;
      input.value = "";
      document.getElementById("filePreview").style.display = "none";
    } else {
      setMsg("uploadMsg", "❌ " + data.message, false);
    }
  } catch (err) {
    setMsg("uploadMsg", "❌ Network error: " + err.message, false);
  }
}

// ── File list ─────────────────────────────────────────────────────────────────
async function loadFiles() {
  try {
    const res  = await fetch(`${API}/files/list`, { headers: authHeaders() });
    const data = await res.json();
    if (!data.success) return;
    renderFileTable("fileList",   data.owned,  false);
    renderFileTable("sharedList", data.shared, true);
  } catch (err) {
    document.getElementById("fileList").innerHTML =
      `<p class="error">Network error: ${err.message}</p>`;
  }
}

function renderFileTable(containerId, files, isShared) {
  const el = document.getElementById(containerId);
  if (!files || files.length === 0) {
    el.innerHTML = `<p class="hint">No files found.</p>`;
    return;
  }

  const rows = files.map(f => `
    <tr>
      <td>${escHtml(f.original_name)}</td>
      <td class="hash-cell" title="${escHtml(f.blockchain_hash)}">
        ${escHtml(f.blockchain_hash.substring(0,16))}…
      </td>
      <td>${new Date(f.uploaded_at).toLocaleString()}</td>
      ${isShared ? `<td>${escHtml(f.granted_by || "—")}</td>` : ""}
      <td class="actions">
        <button class="btn-sm btn-green"
                onclick="doDownload(${f.id}, '${escHtml(f.original_name)}')">
          ⬇ Download
        </button>
        <button class="btn-sm btn-blue"
                onclick="openVerify(${f.id}, '${escHtml(f.original_name)}')">
          ✅ Verify
        </button>
        ${!isShared ? `
        <button class="btn-sm btn-orange"
                onclick="openShare(${f.id}, '${escHtml(f.original_name)}')">
          🔗 Share
        </button>` : ""}
      </td>
    </tr>
  `).join("");

  el.innerHTML = `
    <table class="file-table">
      <thead>
        <tr>
          <th>Filename</th>
          <th>Hash (short)</th>
          <th>Uploaded</th>
          ${isShared ? "<th>Shared By</th>" : ""}
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>`;
}

// ── Download ──────────────────────────────────────────────────────────────────
async function doDownload(fileId, filename) {
  try {
    const res = await fetch(`${API}/files/download/${fileId}`, {
      headers: authHeaders()
    });

    if (!res.ok) {
      const data = await res.json();
      alert("❌ " + data.message);
      return;
    }

    const blob = await res.blob();
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href     = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  } catch (err) {
    alert("❌ Download failed: " + err.message);
  }
}

// ── Verify ────────────────────────────────────────────────────────────────────
function openVerify(fileId, filename) {
  document.getElementById("verifyFileName").textContent = filename;
  document.getElementById("verifyResult").innerHTML = "⏳ Verifying…";
  document.getElementById("verifyModal").style.display = "flex";
  doVerify(fileId);
}

async function doVerify(fileId) {
  try {
    const res  = await fetch(`${API}/files/verify/${fileId}`, { headers: authHeaders() });
    const data = await res.json();
    const ok   = data.integrity_ok;
    document.getElementById("verifyResult").innerHTML = `
      <div class="verify-row ${ok ? "ok" : "fail"}">
        <strong>Local Integrity:</strong>
        ${ok ? "✅ File intact" : "❌ File may be tampered!"}
      </div>
      <div class="verify-row ${data.blockchain_ok === true ? "ok" : data.blockchain_ok === false ? "fail" : "warn"}">
        <strong>Blockchain:</strong>
        ${data.blockchain_ok === true  ? "✅ Hash found on-chain" :
          data.blockchain_ok === false ? "❌ Hash not found on-chain" :
          "⚠️ Ganache offline"}
      </div>
      <div class="hash-detail">
        <strong>Stored Hash:</strong><br>
        <code>${data.stored_hash}</code>
      </div>`;
  } catch (err) {
    document.getElementById("verifyResult").textContent = "❌ Verify failed: " + err.message;
  }
}

function closeVerifyModal() {
  document.getElementById("verifyModal").style.display = "none";
}

// ── Share modal ───────────────────────────────────────────────────────────────
let _shareFileId = null;

function openShare(fileId, filename) {
  _shareFileId = fileId;
  document.getElementById("shareFileName").textContent = filename;
  document.getElementById("shareTarget").value = "";
  setMsg("shareMsg", "", true);
  document.getElementById("shareModal").style.display = "flex";
}

function closeModal() {
  document.getElementById("shareModal").style.display = "none";
}

async function doShare() {
  const target = document.getElementById("shareTarget").value.trim();
  if (!target) return setMsg("shareMsg", "Enter a username.", false);

  try {
    const res  = await fetch(`${API}/files/share`, {
      method: "POST",
      headers: authHeadersJSON(),
      body: JSON.stringify({ file_id: _shareFileId, share_to: target })
    });
    const data = await res.json();
    setMsg("shareMsg", data.message, data.success);
    if (data.success) setTimeout(closeModal, 1200);
  } catch (err) {
    setMsg("shareMsg", "Network error: " + err.message, false);
  }
}

// ── XSS helper ────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g,"&amp;").replace(/</g,"&lt;")
    .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
