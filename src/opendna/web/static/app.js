const $ = (id) => document.getElementById(id);
let lastReport = null;

// --- Preference storage (browser-local, never sent over network) ----
// Values stay in the browser's localStorage for the current origin
// (http://localhost:8787). They are NOT written to disk by the server,
// committed to git, or transmitted anywhere. Clearing them here is
// sufficient to remove them.
const STORAGE_KEY = "opendna:preferences";

function loadStoredPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const prefs = JSON.parse(raw);
    if (prefs.filePath) $("file-path").value = prefs.filePath;
    if (prefs.llmProvider) $("llm-provider").value = prefs.llmProvider;
    if (prefs.llmModel) $("llm-model").value = prefs.llmModel;
    if (prefs.apiKey) $("llm-key").value = prefs.apiKey;
    if (typeof prefs.remember === "boolean") $("remember").checked = prefs.remember;
  } catch {
    // storage disabled or corrupt — fall through to blank form
  }
}

function saveStoredPrefs() {
  if (!$("remember").checked) return;
  const prefs = {
    filePath: $("file-path").value.trim(),
    llmProvider: $("llm-provider").value,
    llmModel: $("llm-model").value,
    apiKey: $("llm-key").value,
    remember: true,
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // storage full / disabled — silent; form still works for this session
  }
}

function clearStoredPrefs() {
  try { localStorage.removeItem(STORAGE_KEY); } catch {}
  $("file-path").value = "";
  $("llm-provider").value = "";
  $("llm-model").value = "";
  $("llm-key").value = "";
  $("remember").checked = true;
  setStatus("Cleared saved values.", false);
}

function renderPanelCheckbox(panel) {
  const label = document.createElement("label");

  const checkbox = document.createElement("input");
  checkbox.type = "checkbox";
  checkbox.value = panel.id;
  checkbox.checked = true;

  const text = document.createElement("span");
  const name = document.createElement("strong");
  name.textContent = panel.name;
  const count = document.createElement("span");
  count.style.color = "var(--dim)";
  count.textContent = " (" + panel.snp_count + ")";
  text.appendChild(name);
  text.appendChild(count);

  label.appendChild(checkbox);
  label.appendChild(text);
  return label;
}

async function loadPanels() {
  const resp = await fetch("/api/panels");
  const { panels } = await resp.json();
  const container = $("panels");
  container.replaceChildren(...panels.map(renderPanelCheckbox));
}

function selectedPanels() {
  return Array.from(document.querySelectorAll('#panels input:checked')).map(el => el.value);
}

function llmConfig() {
  const provider = $("llm-provider").value;
  if (!provider) return null;
  return {
    provider,
    model: $("llm-model").value || (provider === "anthropic" ? "claude-sonnet-4-6" : "gpt-4o"),
    api_key: $("llm-key").value,
  };
}

function download(filename, content, mime) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click();
  document.body.removeChild(a); URL.revokeObjectURL(url);
}

function setStatus(message, isError) {
  const status = $("status");
  status.className = isError ? "status error" : "status";
  status.textContent = message;
}

// --- Progress UI --------------------------------------------------

function resetProgress() {
  $("progress").classList.remove("hidden");
  $("progress-fill").style.width = "0%";
  $("progress-current").replaceChildren();
  $("progress-log").replaceChildren();
}

function hideProgress() {
  $("progress").classList.add("hidden");
}

let _lastLoggedMessage = null;

function setProgress(pct, message) {
  $("progress-fill").style.width = Math.min(100, Math.max(0, pct)) + "%";

  // Update the "currently doing" line.
  const current = $("progress-current");
  current.replaceChildren();
  const pctSpan = document.createElement("span");
  pctSpan.className = "pct";
  pctSpan.textContent = Math.round(pct) + "%";
  const msgSpan = document.createElement("span");
  msgSpan.textContent = message;
  current.appendChild(pctSpan);
  current.appendChild(msgSpan);

  // Append the previous step to the log (so the current one isn't duplicated).
  if (_lastLoggedMessage && _lastLoggedMessage !== message) {
    const li = document.createElement("li");
    li.textContent = _lastLoggedMessage;
    $("progress-log").appendChild(li);
  }
  _lastLoggedMessage = message;
}

function logError(message) {
  const li = document.createElement("li");
  li.className = "error";
  li.textContent = message;
  $("progress-log").appendChild(li);
}

// --- SSE consumer -------------------------------------------------

function parseSSEEvent(raw) {
  const lines = raw.split("\n");
  const event = { type: "message", data: null };
  for (const line of lines) {
    if (line.startsWith("event: ")) event.type = line.slice(7).trim();
    else if (line.startsWith("data: ")) {
      try { event.data = JSON.parse(line.slice(6)); }
      catch { event.data = line.slice(6); }
    }
  }
  return event;
}

async function consumeStream(resp, onEvent) {
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sepIdx;
    while ((sepIdx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, sepIdx);
      buffer = buffer.slice(sepIdx + 2);
      if (!raw.trim()) continue;
      onEvent(parseSSEEvent(raw));
    }
  }
}

async function run() {
  const btn = $("run");
  _lastLoggedMessage = null;
  resetProgress();
  setStatus("", false);
  btn.disabled = true;

  try {
    const body = {
      file_path: $("file-path").value.trim(),
      selected_panels: selectedPanels(),
      llm: llmConfig(),
    };
    if (!body.file_path) throw new Error("Enter the path to your raw DNA file.");
    if (!body.selected_panels.length) throw new Error("Select at least one panel.");

    saveStoredPrefs();

    const resp = await fetch("/api/analyze-stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ detail: resp.statusText }));
      throw new Error(err.detail || "Request failed");
    }

    let completed = false;
    await consumeStream(resp, (event) => {
      if (event.type === "progress") {
        setProgress(event.data.pct, event.data.message);
      } else if (event.type === "complete") {
        setProgress(100, "Done");
        lastReport = {
          report_html: event.data.report_html,
          report_json: event.data.report_json,
        };
        $("report-iframe").srcdoc = event.data.report_html;
        $("report-frame").classList.remove("hidden");
        const n = event.data.report_json.findings_count;
        setStatus("Report ready — " + n + " findings.", false);
        completed = true;
      } else if (event.type === "error") {
        logError(event.data.detail);
        throw new Error(event.data.detail);
      }
    });

    if (!completed) throw new Error("Stream ended without a completion event.");
  } catch (err) {
    setStatus(err.message, true);
  } finally {
    btn.disabled = false;
  }
}

$("run").addEventListener("click", run);
$("download-html").addEventListener("click", () => {
  if (lastReport) download("opendna-report.html", lastReport.report_html, "text/html");
});
$("download-json").addEventListener("click", () => {
  if (lastReport) download("opendna-report.json", JSON.stringify(lastReport.report_json, null, 2), "application/json");
});
$("clear-saved").addEventListener("click", clearStoredPrefs);
$("remember").addEventListener("change", () => {
  if (!$("remember").checked) {
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
  }
});

loadStoredPrefs();
loadPanels();
