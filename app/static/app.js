"use strict";

// The DOM boundary uses textContent exclusively for source data and generated output.
const $ = (selector) => document.querySelector(selector);
const state = { dataset: null, analysis: null, brief: null, offset: 0, totalRows: 0, ai: false, busy: false };
const roles = { ward: "Ward officer", society: "Housing society", school: "School team" };
const labels = { station: "Location / monitor", timestamp: "Observation time", pollutant: "Pollutant", value: "Concentration", unit: "Measurement unit", duration_hours: "Averaging period (hours)" };
const number = (value) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 3 }).format(value);
const date = (value) => value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeZone: "Asia/Kolkata" }).format(new Date(value)) : "Not supplied";
const humanize = (text) => text.replaceAll("_", " ");
const scrollBehavior = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth";

function node(tag, attributes = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(attributes)) {
    if (key === "class") element.className = value;
    else if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
    else if (value !== false && value != null) element.setAttribute(key, value === true ? "" : String(value));
  }
  for (const child of children.flat(Infinity)) {
    if (child != null) element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return element;
}

function svgNode(tag, attributes = {}, ...children) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, String(value));
  for (const child of children) element.append(child instanceof Node ? child : document.createTextNode(String(child)));
  return element;
}

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const data = await response.json();
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Check the submitted values and try again.";
    throw new Error(detail);
  }
  return data;
}
const post = (path, payload) => api(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });

function notice(message, error = false) {
  const box = $("#notice");
  box.textContent = message;
  box.classList.toggle("error", error);
  box.hidden = !message;
  box.setAttribute("role", error ? "alert" : "status");
  if (error) box.scrollIntoView({ behavior: scrollBehavior(), block: "nearest" });
}

async function task(button, operation) {
  if (state.busy) return;
  state.busy = true;
  document.body.classList.add("loading");
  const content = button?.textContent;
  if (button) { button.disabled = true; button.textContent = "Working…"; button.setAttribute("aria-busy", "true"); }
  try { await operation(); }
  catch (error) { notice(error.message || "Something went wrong. Please try again.", true); }
  finally {
    state.busy = false;
    document.body.classList.remove("loading");
    if (button) { button.disabled = false; button.textContent = content; button.removeAttribute("aria-busy"); }
  }
}

function navigate(view, focus = true) {
  document.querySelectorAll(".view").forEach((section) => { section.hidden = section.id !== `view-${view}`; });
  document.querySelectorAll(".nav-button").forEach((button) => {
    const active = button.dataset.view === view;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page"); else button.removeAttribute("aria-current");
  });
  $("#breadcrumb").textContent = { intake: "Data intake", evidence: "Evidence room", briefing: "Briefing studio", archive: "Brief archive" }[view];
  if (view === "archive") task(null, loadArchive);
  if (focus) { $("#main").focus({ preventScroll: true }); window.scrollTo({ top: 0, behavior: scrollBehavior() }); }
}

function table(target, headings, records, caption = "") {
  const element = $(target);
  element.replaceChildren();
  if (caption) element.append(node("caption", {}, caption));
  element.append(node("thead", {}, node("tr", {}, headings.map((heading) => node("th", { scope: "col" }, heading)))));
  const body = node("tbody");
  for (const record of records) body.append(node("tr", {}, record.map((cell) => node("td", {}, cell))));
  element.append(body);
}

function resetAfterImport() {
  state.analysis = null; state.brief = null; state.offset = 0;
  $("#mapping-confirm").checked = false;
  $("#evidence-content").hidden = true; $("#evidence-empty").hidden = false;
  $("#brief-content").hidden = true; $("#brief-empty").hidden = false;
}

function showImport(data) {
  resetAfterImport(); state.dataset = data;
  $("#import-meta").textContent = `${data.filename} · ${number(data.row_count)} source rows · SHA-256 ${data.sha256.slice(0, 16)}…`;
  table("#preview-table", ["Source row", ...data.columns], data.preview.map((row) => [row.source_row, ...data.columns.map((column) => row.cells[column])]), "Source preview — first eight data rows");
  const fields = $("#mapping-fields"); fields.replaceChildren();
  for (const [field, label] of Object.entries(labels)) {
    const select = node("select", { id: `map-${field}` }, node("option", { value: "" }, "Not mapped"), data.columns.map((column) => node("option", { value: column }, column)));
    select.value = data.mapping[field] || "";
    fields.append(node("label", { for: `map-${field}` }, label, select, node("span", {}, ["station", "timestamp", "value"].includes(field) ? "Required" : field === "duration_hours" ? "Optional · needed for WHO comparison" : "Map a column or confirm a fixed value below")));
  }
  $("#fixed-pollutant").value = ""; $("#fixed-unit").value = "";
  $("#mapping-section").hidden = false;
  notice(`Read ${number(data.row_count)} rows. Review the mapping before analysis.`);
  $("#mapping-section").scrollIntoView({ behavior: scrollBehavior(), block: "start" });
}

async function upload(file) {
  if (!file) return;
  if (file.size > 5 * 1024 * 1024) throw new Error("Choose a file no larger than 5 MB.");
  const form = new FormData(); form.append("file", file);
  showImport(await api("/api/import", { method: "POST", body: form }));
}

async function analyze() {
  if (!state.dataset) throw new Error("Import a table first.");
  if (!$("#mapping-confirm").checked) throw new Error("Review the import settings and tick the confirmation before analysis.");
  const mapping = Object.fromEntries(Object.keys(labels).map((field) => [field, $(`#map-${field}`).value]));
  const result = await post(`/api/datasets/${state.dataset.id}/analyze`, { mapping, options: { pollutant: $("#fixed-pollutant").value, unit: $("#fixed-unit").value, date_order: $("#date-order").value } });
  state.analysis = result.analysis; state.offset = 0;
  state.brief = null; $("#brief-content").hidden = true; $("#brief-empty").hidden = false;
  renderAnalysis();
  await loadRows();
  navigate("evidence");
  notice(`${number(result.analysis.included)} readings included; ${number(result.analysis.excluded)} excluded. Inspect the ledger before briefing.`);
}

function renderAnalysis() {
  const analysis = state.analysis;
  $("#evidence-empty").hidden = true; $("#evidence-content").hidden = false;
  $("#evidence-source").textContent = `${state.dataset.filename} · ${date(analysis.start)} — ${date(analysis.end)} · concentrations normalized to µg/m³ · SHA-256 ${state.dataset.sha256.slice(0, 16)}…`;
  $("#metric-grid").replaceChildren(...[
    ["SOURCE READINGS", analysis.total, "Every supplied nonempty data row"],
    ["INCLUDED", analysis.included, "Valid after normalization"],
    ["NEEDS ATTENTION", analysis.flagged, `${analysis.excluded} excluded · outliers retained`],
    ["MONITOR LOCATIONS", analysis.stations, "Observed locations, not city coverage"],
  ].map(([label, value, description]) => node("div", { class: "metric" }, node("span", { class: "eyebrow" }, label), node("strong", {}, number(value)), node("small", {}, description))));
  const pollutants = [...new Set(analysis.summaries.map((summary) => summary.pollutant))].sort();
  $("#pollutant-filter").replaceChildren(...pollutants.map((pollutant) => node("option", { value: pollutant }, pollutant)));
  const flags = Object.entries(analysis.flags);
  $("#quality-flags").replaceChildren(...(flags.length ? flags.map(([flag, count]) => node("span", { class: `flag-chip ${flag.includes("invalid") || flag.includes("conflicting") || flag.includes("unknown") ? "warning" : ""}` }, `${humanize(flag)} · ${count}`)) : [node("p", { class: "fine-print" }, "No parsing or statistical flags detected. This does not verify monitor accuracy or sampling completeness.")]));
  $("#quality-flags").append(node("p", { class: "fine-print" }, "Missing sampling coverage is unknown. Zero flags is not a clean-air certification."));
  $("#limitations-list").replaceChildren(...analysis.limitations.map((limit) => node("li", {}, limit)));
  renderCharts();
}

function receiptButton(ids, briefId = null) {
  return node("button", { class: "receipt-link", onclick: () => task(null, () => showReceipt(ids, briefId)) }, `Trace ${number(ids.length)} source row${ids.length === 1 ? "" : "s"} ↗`);
}

async function showReceipt(ids, briefId) {
  const limitedIds = ids.slice(0, 100);
  const route = briefId ? `/api/briefs/${briefId}/rows` : `/api/datasets/${state.dataset.id}/rows`;
  const result = await api(`${route}?ids=${encodeURIComponent(limitedIds.join(","))}`);
  $("#receipt-meta").textContent = `Showing ${result.rows.length} of ${number(ids.length)} linked rows. Download the evidence pack for the complete snapshot.`;
  table("#receipt-table", ["Row", "Location / pollutant", "Normalized", "Source cells", "Flags"], result.rows.map((row) => [row.id, `${row.station} · ${row.pollutant || "unknown"}`, row.value == null ? "Excluded / unavailable" : `${number(row.value)} µg/m³`, node("div", { class: "receipt-raw" }, Object.entries(row.raw).map(([key, value]) => `${key}: ${value}`).join("\n")), row.flags.map(humanize).join(", ") || "—"]));
  $("#evidence-dialog").showModal();
}

function renderCharts() {
  const pollutant = $("#pollutant-filter").value;
  const summaries = state.analysis.summaries.filter((summary) => summary.pollutant === pollutant).sort((a, b) => a.rank - b.rank);
  const maximum = Math.max(...summaries.map((summary) => summary.mean), 1);
  const chart = $("#station-chart"); chart.replaceChildren();
  if (summaries.length > 12) chart.append(node("p", { class: "fine-print" }, `Showing the top 12 of ${number(summaries.length)} locations. The source ledger and exports retain every reading.`));
  for (const summary of summaries.slice(0, 12)) {
    const bar = svgNode("svg", { viewBox: "0 0 400 8", preserveAspectRatio: "none", "aria-hidden": "true" }, svgNode("rect", { width: 400, height: 8, fill: "#e7ebde", rx: 1 }), svgNode("rect", { width: Math.max(0, summary.mean / maximum * 400), height: 8, fill: summary.rank === 1 ? "#a73e25" : "#67805c", rx: 1 }));
    chart.append(node("div", { class: "station-item" }, node("div", { class: "station-row" }, node("div", {}, node("strong", {}, `${String(summary.rank).padStart(2, "0")} / ${summary.station}`), node("small", {}, `${summary.count} readings · median ${number(summary.median)} · p95 ${number(summary.p95)}`)), node("strong", {}, `${number(summary.mean)} µg/m³`)), bar, receiptButton(summary.evidence)));
  }
  if (!summaries.length) chart.append(node("p", { class: "no-data-note" }, "No valid readings to rank. Review excluded rows and import settings."));
  const allTrends = state.analysis.trends.filter((trend) => trend.pollutant === pollutant);
  const trends = allTrends.slice(-90);
  const target = $("#trend-chart"); target.replaceChildren();
  if (!trends.length) { target.append(node("p", { class: "no-data-note" }, "A timeline needs valid dated readings.")); return; }
  if (allTrends.length > 90) target.append(node("p", { class: "fine-print" }, `Chart shows the latest 90 of ${number(allTrends.length)} observation days. Export retains all readings.`));
  const width = 440, height = 170;
  const times = trends.map((trend) => new Date(trend.date).getTime());
  const start = Math.min(...times), span = Math.max(...times) - start || 1;
  const max = Math.max(...trends.map((trend) => trend.mean), 1);
  const svg = svgNode("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": `${pollutant} daily sample means. See the values table below.` }, svgNode("title", {}, `${pollutant}: daily sample means, µg/m³`));
  for (let i = 0; i <= 3; i++) {
    const y = 14 + i * 42;
    svg.append(svgNode("line", { x1: 42, x2: 425, y1: y, y2: y, stroke: "#d4d8cb", "stroke-dasharray": "3 4" }), svgNode("text", { x: 0, y: y + 3, fill: "#58655c", "font-size": 9 }, number(max * (1 - i / 3))));
  }
  trends.forEach((trend, index) => {
    const x = trends.length === 1 ? 230 : 48 + ((times[index] - start) / span) * 370;
    const y = 140 - trend.mean / max * 126;
    svg.append(svgNode("line", { x1: x, x2: x, y1: 140, y2: y, stroke: "#93a787", "stroke-width": 2 }), svgNode("circle", { cx: x, cy: y, r: 4, fill: "#a73e25" }, svgNode("title", {}, `${trend.date}: ${trend.mean} µg/m³; ${trend.count} readings`)));
  });
  svg.append(svgNode("text", { x: 44, y: 161, fill: "#58655c", "font-size": 9 }, trends[0].date), svgNode("text", { x: 425, y: 161, "text-anchor": "end", fill: "#58655c", "font-size": 9 }, trends.at(-1).date));
  target.append(svg);
  const details = node("details", {}, node("summary", { class: "fine-print" }, `View ${trends.length} daily values`));
  const wrapper = node("div", { class: "table-wrap" });
  const trendTable = node("table", {}, node("thead", {}, node("tr", {}, ["Date (UTC)", "Mean µg/m³", "Readings"].map((label) => node("th", { scope: "col" }, label)))), node("tbody", {}, trends.map((trend) => node("tr", {}, node("td", {}, trend.date), node("td", {}, number(trend.mean)), node("td", {}, trend.count)))));
  wrapper.append(trendTable); details.append(wrapper); target.append(details);
}

async function loadRows() {
  if (!state.dataset || !state.analysis) return;
  const result = await api(`/api/datasets/${state.dataset.id}/rows?offset=${state.offset}&flagged=${$("#flagged-only").checked}`);
  state.totalRows = result.total;
  table("#ledger-table", ["Source", "Location", "Time (UTC)", "Pollutant", "µg/m³", "Period (h)", "Disposition"], result.rows.map((row) => [receiptButton([row.id]), row.station || "Missing", row.timestamp?.replace("T", " ").replace("+00:00", "") || "Invalid", row.pollutant || "Unknown", row.value == null ? "—" : number(row.value), row.duration_hours ?? "Unknown", node("span", { class: row.included ? "" : "row-excluded" }, `${row.included ? "Included" : "Excluded"}${row.flags.length ? ` · ${row.flags.map(humanize).join(", ")}` : ""}`)]), "All concentrations are normalized to µg/m³. Raw cells are available through each source link.");
  $("#row-count").textContent = result.total ? `Rows ${state.offset + 1}–${state.offset + result.rows.length} of ${number(result.total)}` : "No rows match this filter.";
  $("#prev-rows").disabled = state.offset === 0; $("#next-rows").disabled = state.offset + 100 >= result.total;
}

async function compose() {
  if (!state.dataset || !state.analysis) throw new Error("Import and analyse a table in Data intake first.");
  const result = await post("/api/briefs", { dataset_id: state.dataset.id, role: $("#role").value, language: $("#language").value, reading_level: $("#reading-level").value, use_ai: $("#use-ai").checked });
  renderBrief(result);
  notice(result.mode === "gemini" ? "AI evidence selection passed validation. Review the draft before distribution." : "Rules-based brief saved. GenAI was not used for this draft.");
}

function renderBrief(brief) {
  state.brief = brief;
  const rendered = brief.rendered;
  $("#brief-empty").hidden = true; $("#brief-content").hidden = false;
  $("#brief-meta").textContent = `${roles[brief.role]} · ${date(brief.created_at)} · ${brief.mode === "gemini" ? "Gemini-selected evidence" : "Rules-based · no AI"} · ${brief.source_sha256.slice(0, 12)}…`;
  $("#internal-heading").textContent = rendered.internal_title;
  $("#internal-findings").setAttribute("lang", rendered.language);
  $("#internal-findings").replaceChildren(...rendered.findings.map((finding) => node("div", { class: "finding" }, node("p", {}, finding.text), receiptButton(finding.evidence, brief.id))));
  $("#action-list").setAttribute("lang", rendered.language);
  $("#action-list").replaceChildren(...rendered.actions.map((action) => node("li", {}, action.text, node("div", {}, node("small", { class: "fine-print" }, `Proposed action ${action.id} · linked findings ${action.evidence.join(", ")}`)))));
  $("#brief-quality").textContent = `${brief.analysis.included} of ${brief.analysis.total} readings included; ${brief.analysis.flagged} flagged. ${brief.analysis.limitations.join(" ")}`;
  $(".citizen-note").setAttribute("lang", rendered.language);
  $("#citizen-heading").textContent = rendered.title;
  $("#citizen-date").textContent = `${date(brief.analysis.start)} — ${date(brief.analysis.end)} · ${brief.reading_level === "simple" ? "Easy reading" : "Standard"}`;
  $("#citizen-findings").replaceChildren(...rendered.findings.map((finding) => node("div", { class: "finding" }, node("p", {}, finding.text), receiptButton(finding.evidence, brief.id))));
  $("#care-heading").textContent = { en: "Extra care", hi: "अधिक देखभाल", mr: "अधिक काळजी" }[rendered.language];
  $("#citizen-care").textContent = rendered.care;
  $("#citizen-caveat").textContent = rendered.caveat;
  $("#citizen-review").textContent = rendered.review;
  const comparison = brief.comparison;
  $("#comparison-message").textContent = `${comparison.message}${brief.previous_brief_id ? ` Baseline brief: ${brief.previous_brief_id.slice(0, 8)}.` : ""}`;
  $("#comparison-table").hidden = !comparison.changes.length;
  if (comparison.changes.length) table("#comparison-table", ["Location / pollutant", "Previous mean", "Current mean", "Change", "Comparability"], comparison.changes.map((change) => [`${change.station} / ${change.pollutant}`, change.before == null ? "—" : `${number(change.before)} µg/m³ (n=${change.before_count})`, change.after == null ? "—" : `${number(change.after)} µg/m³ (n=${change.after_count})`, change.status !== "matched" ? humanize(change.status) : `${change.delta > 0 ? "+" : ""}${number(change.delta)} µg/m³${change.percent == null ? " · % undefined from zero" : ` (${change.percent > 0 ? "+" : ""}${change.percent}%)`}`, change.status === "matched" ? change.same_duration ? "Same stated averaging periods; sample windows may differ" : "Averaging periods differ or are unknown; interpret with caution" : "No matched pair"]), "Snapshot changes by matched location and pollutant. Evidence IDs are preserved in the downloadable pack.");
}

async function loadArchive() {
  const briefs = await api("/api/briefs");
  const archive = $("#archive-list"); archive.replaceChildren();
  if (!briefs.length) {
    archive.append(node("div", { class: "empty-state" }, node("span", {}, "≋"), node("h2", {}, "The first brief starts the record."), node("p", {}, "Saved briefs appear here for 24 hours. The next brief for the same audience compares against the last one.")));
    return;
  }
  for (const brief of briefs) archive.append(node("article", { class: "archive-item" }, node("div", {}, node("span", { class: "eyebrow" }, `${date(brief.created_at)} / ${brief.language.toUpperCase()}`), node("h2", {}, roles[brief.role]), node("p", {}, `${brief.filename} · ${brief.mode === "gemini" ? "Gemini-selected" : "Rules-based"} · ${brief.id.slice(0, 8)}`)), node("button", { class: "button secondary", onclick: (event) => task(event.currentTarget, async () => { renderBrief(await api(`/api/briefs/${brief.id}`)); navigate("briefing"); notice("Opened a saved snapshot. Its evidence remains linked to the original import."); }) }, "Open brief ↗")));
}

document.querySelectorAll("[data-view]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.view)));
document.querySelectorAll("[data-go]").forEach((button) => button.addEventListener("click", () => navigate(button.dataset.go)));
$("#file-input").addEventListener("change", (event) => { const file = event.target.files[0]; task(null, () => upload(file)); event.target.value = ""; });
const dropzone = $("#dropzone");
["dragenter", "dragover"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.add("drag-over"); }));
["dragleave", "drop"].forEach((type) => dropzone.addEventListener(type, (event) => { event.preventDefault(); dropzone.classList.remove("drag-over"); }));
dropzone.addEventListener("drop", (event) => { if (event.dataTransfer.files.length !== 1) { notice("Drop one table at a time.", true); return; } task(null, () => upload(event.dataTransfer.files[0])); });
$("#paste-button").addEventListener("click", (event) => task(event.currentTarget, async () => { if (!$("#paste-input").value.trim()) throw new Error("Paste a table including its header row."); showImport(await post("/api/paste", { text: $("#paste-input").value })); }));
$("#analyze-button").addEventListener("click", (event) => task(event.currentTarget, analyze));
$("#suggest-button").addEventListener("click", (event) => task(event.currentTarget, async () => { if (!state.dataset) return; const result = await post(`/api/datasets/${state.dataset.id}/suggest-mapping`, {}); for (const [field, column] of Object.entries(result.mapping)) $(`#map-${field}`).value = column; $("#mapping-confirm").checked = false; notice("AI suggested a mapping. Review each column and confirm before analysis."); }));
$("#pollutant-filter").addEventListener("change", renderCharts);
$("#flagged-only").addEventListener("change", () => task(null, async () => { state.offset = 0; await loadRows(); }));
$("#prev-rows").addEventListener("click", () => task(null, async () => { state.offset = Math.max(0, state.offset - 100); await loadRows(); }));
$("#next-rows").addEventListener("click", () => task(null, async () => { state.offset += 100; await loadRows(); }));
$("#to-brief").addEventListener("click", () => navigate("briefing"));
$("#generate-button").addEventListener("click", (event) => task(event.currentTarget, compose));
$("#export-csv").addEventListener("click", () => { if (state.dataset) window.location.assign(`/api/datasets/${state.dataset.id}/export`); });
$("#export-brief").addEventListener("click", () => { if (state.brief) window.location.assign(`/api/briefs/${state.brief.id}/export`); });
$("#print-button").addEventListener("click", () => window.print());
$("#close-evidence").addEventListener("click", () => $("#evidence-dialog").close());
$("#method-button").addEventListener("click", () => $("#method-dialog").showModal());
$("#close-method").addEventListener("click", () => $("#method-dialog").close());
$("#clear-button").addEventListener("click", (event) => { if (!window.confirm("Delete this session’s uploaded tables and saved briefs? This cannot be undone.")) return; task(event.currentTarget, async () => { await api("/api/workspace", { method: "DELETE" }); state.dataset = null; resetAfterImport(); $("#mapping-section").hidden = true; $("#paste-input").value = ""; navigate("intake"); notice("Workspace cleared. Its uploaded tables and saved briefs were deleted."); }); });

task(null, async () => {
  const status = await api("/api/status"); state.ai = status.ai_configured;
  $("#ai-status").textContent = state.ai ? "● Gemini configured" : "○ AI not connected";
  $("#ai-status").classList.toggle("connected", state.ai);
  $("#use-ai").checked = state.ai; $("#use-ai").disabled = !state.ai;
  $("#suggest-button").disabled = !state.ai;
  $("#suggest-button").title = state.ai ? "Suggest column mappings; your review is required" : "Connect Gemini on the server to enable AI mapping";
  $("#ai-explainer").textContent = state.ai ? "Computed facts and location labels are shared with Gemini. AI can select evidence, never add measurements." : "AI is not connected. Rules-based briefs are available; see the README to connect Gemini.";
});
