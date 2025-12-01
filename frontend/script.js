const API_BASE = "https://smart-task-analyzer-qkzm.onrender.com/";

let tasks = [];
let nextId = 1;

const taskForm = document.getElementById("task-form");
const bulkTextarea = document.getElementById("bulk-json");
const loadBulkBtn = document.getElementById("load-bulk");
const taskTableBody = document.querySelector("#task-table tbody");
const resultsTableBody = document.querySelector("#results-table tbody");
const strategySelect = document.getElementById("strategy");
const analyzeBtn = document.getElementById("analyze-btn");
const suggestBtn = document.getElementById("suggest-btn");
const statusBox = document.getElementById("status-message");

function showStatus(message, type = "info") {
  statusBox.textContent = message || "";
  statusBox.className = "sta-status";
  if (message) {
    statusBox.classList.add(`sta-status-${type}`);
  }
}

function clearStatus() {
  showStatus("");
}

function toNumber(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
}

function parseDependencies(input) {
  if (!input) return [];
  return input
    .split(",")
    .map((x) => x.trim())
    .filter((x) => x !== "" && !Number.isNaN(Number(x)))
    .map((x) => Number(x));
}

function getPriorityLevel(score) {
  if (score >= 1.2) return "high";
  if (score >= 0.7) return "medium";
  return "low";
}

function renderTaskTable() {
  taskTableBody.innerHTML = "";
  tasks.forEach((task) => {
    const tr = document.createElement("tr");

    const deps = task.dependencies.length ? task.dependencies.join(", ") : "-";

    tr.innerHTML = `
      <td>${task.id}</td>
      <td>${task.title}</td>
      <td>${task.due_date || "-"}</td>
      <td>${task.estimated_hours}</td>
      <td>${task.importance}</td>
      <td>${deps}</td>
      <td>
        <button class="btn btn-outline btn-xs" data-remove="${task.id}">
          Remove
        </button>
      </td>
    `;

    taskTableBody.appendChild(tr);
  });

  taskTableBody.querySelectorAll("button[data-remove]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const id = Number(btn.getAttribute("data-remove"));
      tasks = tasks.filter((t) => t.id !== id);
      renderTaskTable();
    });
  });
}

function renderResultsTable(results) {
  resultsTableBody.innerHTML = "";

  results.forEach((task) => {
    const tr = document.createElement("tr");
    const level = getPriorityLevel(task.score);
    let label = "Low";
    if (level === "high") label = "High";
    else if (level === "medium") label = "Medium";

    tr.innerHTML = `
      <td>
        <span class="badge badge-${level}">${label}</span>
      </td>
      <td>${task.title}</td>
      <td>${task.due_date || "-"}</td>
      <td>${task.estimated_hours}</td>
      <td>${task.importance}</td>
      <td>${task.score.toFixed ? task.score.toFixed(2) : task.score}</td>
      <td>${task.explanation}</td>
    `;

    resultsTableBody.appendChild(tr);
  });
}

function renderDependencyGraph() {
  const container = document.getElementById("dep-graph");
  if (!container) return;

  if (!tasks.length) {
    container.innerHTML = 
      "<p style='padding:1.5rem;color:var(--text-muted);text-align:center;'>Add tasks with dependencies to see the graph.</p>";
    return;
  }

  container.innerHTML = 
    "<p style='padding:1.5rem;color:var(--accent);text-align:center;'>Loading visual graph...</p>";

  fetch(`${API_BASE}/graph/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tasks }),
  })
    .then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then(data => {
      if (!window.vis) {
        const script = document.createElement("script");
        script.src = "https://unpkg.com/vis-network/standalone/umd/vis-network.min.js";
        script.onload = () => renderVisNetwork(container, data);
        document.head.appendChild(script);
      } else {
        renderVisNetwork(container, data);
      }
    })
    .catch(err => {
      console.error("Graph error:", err);
      container.innerHTML = 
        "<p style='padding:1.5rem;color:var(--danger);'>Error loading graph.</p>";
    });
}

function renderVisNetwork(container, data) {
  container.innerHTML = "";

  const network = new vis.Network(container, data, {
    height: "400px",
    physics: { enabled: data.nodes.length < 20 },
    layout: { hierarchical: { direction: "UD", sortMethod: "directed" } },
    interaction: { hover: false },
    nodes: {
      shape: "box",
      font: { size: 12, color: "#000000", face: "monospace" },
      borderWidth: 2,
      margin: 8
    },
    edges: {
      arrows: "to",
      color: { 
        color: "#3b82f6", 
        highlight: "#3b82f6" 
      },
      hoverWidth: 0,
      selected: false,
      font: {
        size: 10,
        color: "#ffffff",
        strokeWidth: 0,
        align: "middle"
      }
    }
  });

  network.on("beforeDrawing", (ctx) => {
    data.nodes.forEach(node => {
      const impColor = node.importance >= 8 ? "#ef4444" : 
                      node.importance >= 6 ? "#f59e0b" : "#22c55e";
      ctx.fillStyle = node.inCycle ? "#6b7280" : impColor;
    });
  });
}

taskForm.addEventListener("submit", (e) => {
  e.preventDefault();
  clearStatus();

  const title = taskForm.title.value.trim();
  const dueDate = taskForm.due_date.value || null;
  const hours = toNumber(taskForm.estimated_hours.value, 0);
  const importance = toNumber(taskForm.importance.value, 1);
  const depsInput = taskForm.dependencies.value.trim();
  const dependencies = parseDependencies(depsInput);

  if (!title) {
    showStatus("Please enter a task title.", "error");
    return;
  }
  if (!dueDate) {
    showStatus("Please select a due date.", "error");
    return;
  }
  if (hours < 0) {
    showStatus("Estimated hours cannot be negative.", "error");
    return;
  }
  if (importance < 1 || importance > 10) {
    showStatus("Importance must be between 1 and 10.", "error");
    return;
  }

  const task = {
    id: nextId++,
    title,
    due_date: dueDate,
    estimated_hours: hours,
    importance,
    dependencies,
  };

  tasks.push(task);
  renderTaskTable();
  taskForm.reset();
});

loadBulkBtn.addEventListener("click", () => {
  clearStatus();
  const raw = bulkTextarea.value.trim();
  if (!raw) {
    showStatus("Paste a JSON array of tasks first.", "error");
    return;
  }

  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch (err) {
    showStatus("Invalid JSON. Please check your syntax.", "error");
    return;
  }

  if (!Array.isArray(parsed)) {
    showStatus("JSON must be an array of task objects.", "error");
    return;
  }

  parsed.forEach((item) => {
    const title = String(item.title || `Task ${nextId}`).trim();
    const dueDate = item.due_date || null;
    const hours = toNumber(item.estimated_hours, 0);
    const importance = toNumber(item.importance, 1);
    const dependencies = Array.isArray(item.dependencies)
      ? item.dependencies.map((x) => Number(x))
      : [];

    const task = {
      id: nextId++,
      title,
      due_date: dueDate,
      estimated_hours: hours,
      importance,
      dependencies,
    };
    tasks.push(task);
  });

  renderTaskTable();
  showStatus(`Loaded ${parsed.length} task(s) from JSON.`, "success");
});

async function callApi(endpoint, body) {
  const url = `${API_BASE}/${endpoint}/`;
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }
  return response.json();
}

analyzeBtn.addEventListener("click", async () => {
  clearStatus();

  if (!tasks.length) {
    showStatus("Add at least one task before analyzing.", "error");
    return;
  }

  const strategy = strategySelect.value || "smart_balance";
  showStatus("Analyzing tasks...", "info");

  try {
    const payload = { strategy, tasks };
    const data = await callApi("analyze", payload);
    const results = Array.isArray(data.tasks) ? data.tasks : [];
    renderResultsTable(results);
    renderDependencyGraph();
    showStatus(`Analyzed ${results.length} task(s).`, "success");
  } catch (err) {
    console.error(err);
    showStatus("Error analyzing tasks. Check backend and console.", "error");
  }
});

suggestBtn.addEventListener("click", async () => {
  clearStatus();

  if (!tasks.length) {
    showStatus("Add at least one task before requesting suggestions.", "error");
    return;
  }

  const strategy = strategySelect.value || "smart_balance";
  showStatus("Requesting suggestions...", "info");

  try {
    const payload = { strategy, tasks };
    const data = await callApi("suggest", payload);
    const results = Array.isArray(data.tasks) ? data.tasks : [];
    renderResultsTable(results);
    renderDependencyGraph();
    showStatus(`Suggested ${results.length} task(s) for today.`, "success");
  } catch (err) {
    console.error(err);
    showStatus("Error getting suggestions. Check backend and console.", "error");
  }
});

renderTaskTable();
renderResultsTable([]);
renderDependencyGraph();
