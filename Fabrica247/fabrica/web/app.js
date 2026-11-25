const $ = (id) => document.getElementById(id);
let csrf = "";
let state = {projects: [], workers: [], tasks: [], counts: {}};

async function api(path, options = {}) {
  const headers = {...(options.headers || {})};
  if (options.body) headers["Content-Type"] = "application/json";
  if (csrf && options.method && options.method !== "GET") headers["X-Fabrica-CSRF"] = csrf;
  const response = await fetch(path, {...options, headers, credentials: "same-origin"});
  let data = {};
  try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(data.error || `Error HTTP ${response.status}`);
  return data;
}
function toast(message) {
  const node = $("toast"); node.textContent = message; node.classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => node.classList.remove("show"), 3000);
}
function esc(value) { return String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }
function showLogin() { $("login").classList.remove("hidden"); $("app").classList.add("hidden"); }
function showApp() { $("login").classList.add("hidden"); $("app").classList.remove("hidden"); }
async function boot() {
  const session = await api("/api/session");
  if (!session.authenticated) { showLogin(); return; }
  csrf = session.csrf; showApp(); await refresh();
}
async function refresh() { state = await api("/api/admin/dashboard"); render(); }
function render() {
  const c = state.counts || {};
  $("stats").innerHTML = [
    ["Proyectos", state.projects.length], ["PCs registradas", state.workers.length],
    ["En ejecución", c.RUNNING || 0], ["Pendientes", c.PENDING || 0]
  ].map(([label, val]) => `<div class="stat"><span>${label}</span><strong>${val}</strong></div>`).join("");
  $("projects").innerHTML = state.projects.length ? state.projects.map(p => `
    <div class="project-card">
      <div class="project-chip">${esc(p.name)} · ${esc(p.slug)}</div>
      <label>Prompt permanente del proyecto
        <textarea rows="3" maxlength="8000" data-project-prompt="${esc(p.slug)}" placeholder="Instrucciones que reciben los agentes de este proyecto">${esc(p.agent_prompt || "")}</textarea>
      </label>
      <button class="quiet" data-save-project-prompt="${esc(p.slug)}">Guardar prompt</button>
    </div>`).join("") : '<div class="empty">Todavía no hay proyectos.</div>';
  const select = $("task-project");
  const old = select.value;
  select.innerHTML = state.projects.map(p => `<option value="${esc(p.slug)}">${esc(p.name)}</option>`).join("") || '<option value="">Creá un proyecto primero</option>';
  if (state.projects.some(p => p.slug === old)) select.value = old;
  renderWorkers(); renderTasks();
}
function renderWorkers() {
  const projects = state.projects;
  $("worker-head").innerHTML = `<tr><th>PC / worker</th>${projects.map(p => `<th>${esc(p.name)}<br><span class="worker-meta">Prioridad</span></th>`).join("")}<th>Estado / control</th><th>Prompt del agente</th><th>Acción</th></tr>`;
  if (!state.workers.length) { $("workers").innerHTML = `<tr><td colspan="${projects.length+4}" class="empty">Todavía no hay PCs. Creá una invitación para registrar la primera.</td></tr>`; return; }
  $("workers").innerHTML = state.workers.map(w => {
    const cells = projects.map(p => {
      const pref = w.priorities[String(p.id)] || {priority: 0, enabled: true};
      return `<td><div class="priority-cell"><input aria-label="Prioridad ${esc(w.name)} en ${esc(p.name)}" class="priority-input" type="number" min="-100" max="100" value="${pref.priority}" data-worker="${w.id}" data-project="${p.id}" data-priority><input type="checkbox" title="Habilitado para este proyecto" data-worker="${w.id}" data-project="${p.id}" data-enabled ${pref.enabled ? "checked" : ""}></div></td>`;
    }).join("");
    const status = !w.enabled ? '<span class="offline">Revocado</span>' : (w.online ? (w.desired_state === "PAUSED" ? '<span class="offline">● Pausado</span>' : '<span class="online">● Online</span>') : '<span class="offline">● Offline</span>');
    const remote = w.remote_control
      ? `<div class="worker-meta">Control remoto aceptado</div><button class="quiet" data-toggle-worker="${w.id}" data-state="${w.desired_state}">${w.desired_state === "PAUSED" ? "Reanudar" : "Pausar"}</button>`
      : `<div class="worker-meta">Control remoto no autorizado</div>`;
    const promptCell = w.remote_control
      ? `<textarea rows="3" maxlength="8000" data-worker-prompt="${w.id}" placeholder="Instrucciones específicas para este agente">${esc(w.admin_prompt || "")}</textarea><button class="quiet" data-save-worker-prompt="${w.id}">Guardar</button>`
      : `<span class="worker-meta">El dueño debe habilitarlo localmente</span>`;
    return `<tr><td><div class="worker-name">${esc(w.name)}</div><div class="worker-meta">${esc(w.platform || "Plataforma desconocida")} · ${esc(w.cpu || "CPU sin detectar")} · ${w.cores || "?"} hilos</div><div class="worker-meta">Agente: ${esc(w.agent_label || "sin informar")} · ${esc(w.id.slice(0,8))}</div></td>${cells}<td>${status}<br>${remote}</td><td class="worker-prompt-cell">${promptCell}</td><td>${w.enabled ? `<button class="quiet" data-revoke="${w.id}">Revocar</button>` : "—"}</td></tr>`;
  }).join("");
}
function renderTasks() {
  if (!state.tasks.length) { $("tasks").innerHTML = '<tr><td colspan="9" class="empty">Todavía no hay tareas.</td></tr>'; return; }
  $("tasks").innerHTML = state.tasks.map(t => {
    const status = String(t.status).toLowerCase();
    const desc = t.cancel_requested ? "Detención solicitada al Worker; esperando confirmación" : (t.result || t.last_error || t.branch_name || "—");
    const patch = t.patch_available ? ` · <a class="patch-link" href="/api/admin/tasks/${t.id}/patch">Descargar patch</a>` : "";
    const action = t.status === "FAILED" || t.status === "CANCELLED" ? `<button class="quiet" data-task-retry="${t.id}">Reintentar</button>` : (t.status === "PENDING" ? `<button class="quiet" data-task-cancel="${t.id}">Cancelar</button>` : (t.status === "RUNNING" && t.remote_cancel_allowed && !t.cancel_requested ? `<button class="quiet" data-task-cancel="${t.id}">Detener agente</button>` : "—"));
    return `<tr><td>#${t.id}</td><td>${esc(t.project_name)}</td><td title="${esc(t.objective)}">${esc(t.objective.slice(0,90))}${t.objective.length>90?"…":""}</td><td class="task-prompt-cell"><textarea rows="2" maxlength="8000" data-task-prompt="${t.id}" placeholder="Instrucciones específicas">${esc(t.task_prompt || "")}</textarea><button class="quiet" data-save-task-prompt="${t.id}">Guardar</button></td><td><input class="priority-input" type="number" min="-100" max="100" value="${t.priority}" data-task-priority="${t.id}"></td><td><span class="badge ${status}">${esc(t.status)}</span></td><td>${esc(t.worker_name || "Sin asignar")}</td><td title="${esc(desc)}">${esc(String(desc).slice(0,90))}${patch}</td><td>${action}</td></tr>`;
  }).join("");
}
$("login-form").addEventListener("submit", async e => {
  e.preventDefault(); $("login-error").textContent = "";
  try { const r = await api("/api/login", {method:"POST", body:JSON.stringify({password:$("password").value})}); csrf = r.csrf; $("password").value = ""; showApp(); await refresh(); }
  catch (err) { $("login-error").textContent = err.message; }
});
$("logout").addEventListener("click", async () => { try { await api("/api/logout", {method:"POST",body:"{}"}); } catch (_) {} csrf = ""; showLogin(); });
$("refresh").addEventListener("click", () => refresh().catch(e => toast(e.message)));
$("project-form").addEventListener("submit", async e => {
  e.preventDefault();
  try { await api("/api/admin/projects", {method:"POST", body:JSON.stringify({name:$("project-name").value,slug:$("project-slug").value})}); $("project-form").reset(); await refresh(); toast("Proyecto creado"); }
  catch (err) { toast(err.message); }
});
$("task-form").addEventListener("submit", async e => {
  e.preventDefault();
  try { await api("/api/admin/tasks", {method:"POST", body:JSON.stringify({project_slug:$("task-project").value,objective:$("task-objective").value,task_prompt:$("task-prompt").value,task_type:$("task-type").value,priority:Number($("task-priority").value),max_retries:Number($("task-retries").value),allowed_files:$("task-files").value})}); $("task-objective").value = ""; $("task-prompt").value = ""; $("task-files").value = ""; await refresh(); toast("Tarea agregada a la cola"); }
  catch (err) { toast(err.message); }
});
$("projects").addEventListener("click", async e => {
  const slug = e.target.dataset.saveProjectPrompt;
  if (!slug) return;
  const field = $("projects").querySelector(`[data-project-prompt="${slug}"]`);
  try { await api(`/api/admin/projects/${encodeURIComponent(slug)}/prompt`, {method:"PATCH", body:JSON.stringify({agent_prompt:field.value})}); toast("Prompt del proyecto guardado"); }
  catch (err) { toast(err.message); }
});
$("invite").addEventListener("click", async () => {
  try { const r = await api("/api/admin/invites", {method:"POST", body:JSON.stringify({uses:1,hours:48,label:"Invitación desde dashboard"})}); const box = $("invite-result"); box.classList.remove("hidden"); box.innerHTML = `Código de invitación (válido 48 h, un uso):<br><code>${esc(r.token)}</code> <button id="copy-invite">Copiar</button><p class="muted">Compartilo únicamente con la persona que va a registrar su PC.</p>`; $("copy-invite").addEventListener("click", async () => { await navigator.clipboard.writeText(r.token); toast("Código copiado"); }); }
  catch (err) { toast(err.message); }
});
$("workers").addEventListener("change", async e => {
  const el = e.target;
  if (el.hasAttribute("data-priority") || el.hasAttribute("data-enabled")) {
    const worker_id = el.dataset.worker, project_id = Number(el.dataset.project);
    const row = el.closest("tr");
    const input = row.querySelector(`[data-priority][data-worker="${worker_id}"][data-project="${project_id}"]`);
    const checkbox = row.querySelector(`[data-enabled][data-worker="${worker_id}"][data-project="${project_id}"]`);
    try { await api(`/api/admin/workers/${worker_id}/priority`, {method:"PATCH",body:JSON.stringify({project_id,priority:Number(input.value),enabled:checkbox.checked})}); toast("Prioridad guardada"); }
    catch (err) { toast(err.message); }
  }
});
$("workers").addEventListener("click", async e => {
  const toggle = e.target.dataset.toggleWorker;
  const savePrompt = e.target.dataset.saveWorkerPrompt;
  if (toggle) {
    const current = e.target.dataset.state;
    const desired_state = current === "PAUSED" ? "RUNNING" : "PAUSED";
    const field = $("workers").querySelector(`[data-worker-prompt="${toggle}"]`);
    const admin_prompt = field ? field.value : "";
    try { await api(`/api/admin/workers/${toggle}/control`, {method:"POST", body:JSON.stringify({desired_state, admin_prompt})}); await refresh(); toast(desired_state === "PAUSED" ? "Worker pausado" : "Worker reanudado"); }
    catch (err) { toast(err.message); }
    return;
  }
  if (savePrompt) {
    const field = $("workers").querySelector(`[data-worker-prompt="${savePrompt}"]`);
    try { await api(`/api/admin/workers/${savePrompt}/control`, {method:"POST", body:JSON.stringify({admin_prompt: field.value})}); toast("Instrucciones guardadas"); }
    catch (err) { toast(err.message); }
    return;
  }
  const id = e.target.dataset.revoke; if (!id) return;
  if (!confirm("¿Revocar el acceso de esta PC?")) return;
  try { await api(`/api/admin/workers/${id}/revoke`, {method:"POST",body:"{}"}); await refresh(); toast("Worker revocado"); }
  catch (err) { toast(err.message); }
});
$("tasks").addEventListener("change", async e => {
  const id = e.target.dataset.taskPriority; if (!id) return;
  try { await api(`/api/admin/tasks/${id}`, {method:"PATCH",body:JSON.stringify({priority:Number(e.target.value)})}); toast("Prioridad guardada"); }
  catch (err) { toast(err.message); }
});
$("tasks").addEventListener("click", async e => {
  const savePrompt = e.target.dataset.saveTaskPrompt;
  if (savePrompt) {
    const field = $("tasks").querySelector(`[data-task-prompt="${savePrompt}"]`);
    try { await api(`/api/admin/tasks/${savePrompt}`, {method:"PATCH", body:JSON.stringify({task_prompt:field.value})}); toast("Instrucciones de tarea guardadas"); }
    catch (err) { toast(err.message); }
    return;
  }
  const retry = e.target.dataset.taskRetry, cancel = e.target.dataset.taskCancel;
  const id = retry || cancel; if (!id) return;
  const action = retry ? "retry" : "cancel";
  try { await api(`/api/admin/tasks/${id}/${action}`, {method:"POST",body:"{}"}); await refresh(); toast(retry ? "Tarea reencolada" : "Tarea cancelada"); }
  catch (err) { toast(err.message); }
});
boot().catch(e => { showLogin(); toast(e.message); });
