let appState = null;
let selectedRouteKey = "astar";
let selectedTraceFlightId = null;

async function api(path, method="GET", body=null) {
  const options = { method, headers: {} };
  if (body !== null) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const r = await fetch(path, options);
  const data = await r.json();
  if (!r.ok) {
    alert(data.error || "Request failed.");
    throw new Error(data.error || "Request failed");
  }
  return data;
}

function badge(priority) {
  return `<span class="badge ${priority}">${priority}</span>`;
}

function delayPill(delay, status="normal") {
  const cls = delay > 0 ? "route-delay active" : `route-delay ${status}`;
  return `<span class="${cls}">${delay > 0 ? '+' + delay + ' min' : '0 min'}</span>`;
}

async function refresh() {
  appState = await api("/api/state");
  renderState();
}

function renderState() {
  document.getElementById("scenarioLabel").textContent =
    `Current scenario: ${appState.scenario.replaceAll("_"," ")}.`;

  const runwayCards = document.getElementById("runwayCards");
  runwayCards.innerHTML = appState.runways.map(r => `
    <div class="runway-card ${r.is_open ? 'open-card' : 'closed-card'}">
      <div>
        <strong>${r.runway_id}</strong>
        <div class="state ${r.is_open ? "open" : "closed"}">
          ${r.is_open ? "OPEN" : "CLOSED"}
        </div>
      </div>
      <button onclick="toggleRunway('${r.runway_id}', ${!r.is_open})">
        ${r.is_open ? "Close Runway" : "Open Runway"}
      </button>
    </div>
  `).join("");

  const flightTable = document.getElementById("flightTable");
  flightTable.innerHTML = appState.flights.map(f => `
    <tr class="${f.route_delay > 0 ? 'route-affected-row' : ''}">
      <td><strong>${f.flight_id}</strong></td>
      <td>${f.operation}</td>
      <td>${f.base_eta_label}</td>
      <td>${delayPill(f.route_delay, f.route_status)}</td>
      <td><strong>${f.effective_eta_label}</strong></td>
      <td>${f.aircraft_type}</td>
      <td>${f.fuel_status}</td>
      <td>${badge(f.priority)}</td>
      <td>
        <button onclick="declareEmergency('${f.flight_id}')">Critical Fuel</button>
      </td>
    </tr>
  `).join("");

  document.getElementById("blockedNodes").textContent =
    appState.blocked_waypoints.length
      ? `Blocked waypoints: ${appState.blocked_waypoints.join(", ")}`
      : "No waypoint currently blocked.";

  const log = document.getElementById("eventLog");
  log.innerHTML = appState.logs.slice().reverse()
    .map(x => `&gt; ${x}`).join("<br>");

  fillNodeSelects();
  renderRadar();

  if (appState.last_schedule) {
    renderSchedule(appState.last_schedule);
  } else {
    clearSchedule();
  }

  if (appState.last_routes) {
    renderRoutes(appState.last_routes);
  } else {
    clearRoutes();
  }

  if (appState.last_csp_comparison) {
    renderCspComparison(appState.last_csp_comparison);
  } else {
    clearCspComparison();
  }
}

function fillNodeSelects() {
  const ids = ["weatherNode", "newSource", "routeStart", "routeGoal"];
  ids.forEach(id => {
    const el = document.getElementById(id);
    const current = el.value;
    el.innerHTML = appState.nodes
      .map(n => `<option value="${n}">${n}</option>`).join("");
    if (appState.nodes.includes(current)) el.value = current;
  });

  const routeStart = document.getElementById("routeStart");
  const routeGoal = document.getElementById("routeGoal");
  const newSource = document.getElementById("newSource");
  const weather = document.getElementById("weatherNode");

  if (!routeStart.dataset.initialized) {
    routeStart.value = "NORTH";
    routeStart.dataset.initialized = "1";
  }
  if (!routeGoal.dataset.initialized) {
    routeGoal.value = "AIRPORT";
    routeGoal.dataset.initialized = "1";
  }
  if (!newSource.dataset.initialized) {
    newSource.value = "NORTH";
    newSource.dataset.initialized = "1";
  }
  if (!weather.dataset.initialized) {
    weather.value = appState.scenario === "weather" || appState.scenario === "combined" ? "WP1" : "WP2";
    weather.dataset.initialized = "1";
  }
}

async function loadScenario(name) {
  selectedRouteKey = "astar";
  ["routeStart","routeGoal","weatherNode","newSource"].forEach(id => {
    document.getElementById(id).dataset.initialized = "";
  });
  appState = await api("/api/reset", "POST", {scenario: name});
  renderState();
}

async function toggleRunway(runway_id, is_open) {
  appState = await api("/api/runway", "POST", {runway_id, is_open});
  renderState();
}

async function declareEmergency(flight_id) {
  appState = await api("/api/emergency", "POST", {
    flight_id,
    fuel_status: "critical"
  });
  renderState();
}

async function setWeather(blocked) {
  const node = document.getElementById("weatherNode").value;
  appState = await api("/api/weather", "POST", {node, blocked});
  renderState();
}

async function addFlight() {
  const flight_id = document.getElementById("newFlightId").value.trim();
  if (!flight_id) {
    alert("Enter a flight ID.");
    return;
  }

  appState = await api("/api/flight", "POST", {
    flight_id,
    operation: document.getElementById("newOperation").value,
    eta: Number(document.getElementById("newEta").value),
    aircraft_type: document.getElementById("newType").value,
    fuel_status: document.getElementById("newFuel").value,
    source_waypoint: document.getElementById("newSource").value
  });

  document.getElementById("newFlightId").value = "";
  renderState();
}

async function runScheduler() {
  const button = document.querySelector("button.primary");
  const original = button.textContent;
  button.textContent = "OPTIMIZING...";
  button.disabled = true;
  try {
    const result = await api("/api/schedule", "POST", {});
    appState = await api("/api/state");
    renderState();
    renderSchedule(result);
  } finally {
    button.textContent = original;
    button.disabled = false;
  }
}

function clearSchedule() {
  document.getElementById("scheduleSummary").innerHTML = `
    <div class="metric"><span>Status</span><strong>Not Run</strong></div>
    <div class="metric"><span>Objective</span><strong>Weighted CSP Delay</strong></div>
  `;
  document.getElementById("scheduleTable").innerHTML = "";
  document.getElementById("explanationBox").innerHTML = "";
  clearDecisionTrace();
}

function renderSchedule(result) {
  const summary = document.getElementById("scheduleSummary");
  const table = document.getElementById("scheduleTable");
  const explanations = document.getElementById("explanationBox");
  const s = result.stats || {};

  if (!result.solved) {
    summary.innerHTML = `
      <div class="metric"><span>Status</span><strong>No Solution</strong></div>
      <div class="metric"><span>Candidates</span><strong>${s.candidate_assignments ?? 0}</strong></div>
      <div class="metric"><span>Backtracks</span><strong>${s.backtracks ?? 0}</strong></div>
      <div class="metric"><span>Runtime</span><strong>${s.runtime_ms ?? 0} ms</strong></div>
    `;
    table.innerHTML = "";
    explanations.innerHTML = `<div class="explanation-card">${result.message}</div>`;
    clearDecisionTrace();
    return;
  }

  summary.innerHTML = `
    <div class="metric featured"><span>Status</span><strong>Optimized</strong></div>
    <div class="metric"><span>Weighted CSP Cost</span><strong>${s.best_weighted_cost}</strong></div>
    <div class="metric"><span>Avg Route Delay</span><strong>${s.average_route_delay ?? 0} min</strong></div>
    <div class="metric"><span>Avg CSP Delay</span><strong>${s.average_delay} min</strong></div>
    <div class="metric total-metric"><span>Avg Total Delay</span><strong>${s.average_total_delay ?? s.average_delay} min</strong></div>
    <div class="metric"><span>Emergency CSP Delay</span><strong>${s.emergency_delay} min</strong></div>
    <div class="metric"><span>Emergency Total Delay</span><strong>${s.emergency_total_delay ?? s.emergency_delay} min</strong></div>
    <div class="metric"><span>Candidates</span><strong>${s.candidate_assignments}</strong></div>
    <div class="metric"><span>Constraint Checks</span><strong>${s.constraint_checks}</strong></div>
    <div class="metric"><span>Backtracks</span><strong>${s.backtracks}</strong></div>
    <div class="metric"><span>Pruned Branches</span><strong>${s.branches_pruned}</strong></div>
    <div class="metric"><span>Runtime</span><strong>${s.runtime_ms} ms</strong></div>
    <div class="metric"><span>Fixed Horizon</span><strong>${s.fixed_horizon_used ? "YES" : "NO"}</strong></div>
    <div class="metric"><span>Initial Bound</span><strong>${s.initial_incumbent_cost ?? "—"}</strong></div>
    <div class="metric total-metric"><span>Exact Validator</span><strong>${result.exact_validation?.available ? (result.exact_validation.matches_optimizer ? "MATCH" : "CHECK") : "N/A"}</strong></div>
    <div class="metric"><span>Validated Cost</span><strong>${result.exact_validation?.available ? result.exact_validation.best_weighted_cost : "—"}</strong></div>
    <div class="metric"><span>Orders Checked</span><strong>${result.exact_validation?.available ? result.exact_validation.permutations_checked.toLocaleString() : "—"}</strong></div>
  `;

  table.innerHTML = result.assignments.map(a => `
    <tr>
      <td><strong>${a.flight_id}</strong></td>
      <td>${badge(a.priority)}</td>
      <td>${a.planned_eta_label}</td>
      <td>${delayPill(a.route_delay)}</td>
      <td>${a.effective_eta_label}</td>
      <td><strong>${a.runway_id}</strong></td>
      <td>${a.slot_label}</td>
      <td>${a.delay} min</td>
      <td><strong>${a.total_delay_from_planned} min</strong></td>
      <td>${a.weighted_delay}</td>
      <td><button class="trace-button" onclick="openDecisionTrace('${a.flight_id}')">Trace</button></td>
    </tr>
  `).join("");

  explanations.innerHTML = Object.entries(result.explanations || {})
    .map(([fid, reasons]) => `
      <div class="explanation-card">
        <h4>${fid}: Compact Rationale</h4>
        <ul>${reasons.map(r => `<li>${r}</li>`).join("")}</ul>
      </div>
    `).join("");

  setupDecisionTrace(result);
}

function clearDecisionTrace() {
  selectedTraceFlightId = null;
  const select = document.getElementById("traceFlightSelect");
  if (select) select.innerHTML = `<option value="">Run optimizer first</option>`;
  const summary = document.getElementById("traceSummary");
  if (summary) summary.textContent = "Run the optimizer to generate an end-to-end decision trace.";
  const box = document.getElementById("decisionTrace");
  if (box) box.innerHTML = "";
}

function setupDecisionTrace(result) {
  const traces = result.decision_traces || {};
  const select = document.getElementById("traceFlightSelect");
  const ids = Object.keys(traces);
  if (!ids.length) {
    clearDecisionTrace();
    return;
  }

  select.innerHTML = ids.map(fid => {
    const t = traces[fid];
    return `<option value="${fid}">${fid} · ${t.priority.toUpperCase()}</option>`;
  }).join("");

  if (!selectedTraceFlightId || !traces[selectedTraceFlightId]) {
    const emergency = ids.find(fid => traces[fid].priority === "emergency");
    const high = ids.find(fid => traces[fid].priority === "high");
    selectedTraceFlightId = emergency || high || ids[0];
  }
  select.value = selectedTraceFlightId;
  renderSelectedDecisionTrace();
}

function renderSelectedDecisionTrace() {
  const traces = appState?.last_schedule?.decision_traces || {};
  const select = document.getElementById("traceFlightSelect");
  const requested = select?.value || selectedTraceFlightId;
  if (!requested || !traces[requested]) {
    clearDecisionTrace();
    return;
  }

  selectedTraceFlightId = requested;
  const trace = traces[requested];
  document.getElementById("traceSummary").innerHTML = `
    <div>
      <span class="trace-kicker">END-TO-END EXPLANATION</span>
      <strong>${trace.summary}</strong>
    </div>
    ${badge(trace.priority)}
  `;

  document.getElementById("decisionTrace").innerHTML = trace.stages.map(stage => `
    <article class="trace-stage trace-${stage.tone}">
      <div class="trace-stage-head">
        <span class="trace-code">${stage.code}</span>
        <h3>${stage.title}</h3>
      </div>
      <ul>${stage.items.map(item => `<li>${item}</li>`).join("")}</ul>
    </article>
  `).join("");
}

function openDecisionTrace(flightId) {
  selectedTraceFlightId = flightId;
  const select = document.getElementById("traceFlightSelect");
  if (select) select.value = flightId;
  renderSelectedDecisionTrace();
  document.getElementById("decisionTracePanel")?.scrollIntoView({behavior: "smooth", block: "start"});
}

async function compareCspStrategies() {
  const data = await api("/api/csp-compare", "POST", {});
  appState = await api("/api/state");
  renderState();
  renderCspComparison(data);
}

function clearCspComparison() {
  const wrap = document.getElementById("cspCompareWrap");
  wrap.classList.add("hidden");
  document.getElementById("cspCompareTable").innerHTML = "";
}

function renderCspComparison(data) {
  const wrap = document.getElementById("cspCompareWrap");
  wrap.classList.remove("hidden");
  const solved = data.results.filter(r => r.solved);
  const minBacktracks = solved.length ? Math.min(...solved.map(r => r.stats.backtracks)) : null;
  const minChecks = solved.length ? Math.min(...solved.map(r => r.stats.constraint_checks)) : null;

  document.getElementById("cspCompareTable").innerHTML = data.results.map(r => {
    const s = r.stats;
    return `
      <tr>
        <td><strong>${r.label}</strong></td>
        <td>${r.solved ? '<span class="yes">YES</span>' : '<span class="no">NO</span>'}</td>
        <td>${s.candidate_assignments}</td>
        <td>${s.constraint_checks}${s.constraint_checks === minChecks ? '<span class="mini-tag">FEWEST</span>' : ''}</td>
        <td>${s.backtracks}${s.backtracks === minBacktracks ? '<span class="mini-tag nodes">FEWEST</span>' : ''}</td>
        <td>${s.forward_checks}</td>
        <td>${s.runtime_ms}</td>
      </tr>
    `;
  }).join("");
}

async function compareRoutes() {
  const start = document.getElementById("routeStart").value;
  const goal = document.getElementById("routeGoal").value;
  const data = await api("/api/routes", "POST", {start, goal});
  selectedRouteKey = "astar";
  appState = await api("/api/state");
  renderState();
  renderRoutes(data);
  renderRadar();
}

function clearRoutes() {
  document.getElementById("routeTable").innerHTML = "";
  document.getElementById("routeInsight").innerHTML =
    `<span class="muted">Run a comparison to overlay a route on the radar.</span>`;
  document.getElementById("radarRouteLabel").textContent = "DISPLAYED ROUTE: NONE";
}

function renderRoutes(data) {
  const rows = data.results.map(r => {
    const bestCost = r.found && r.cost === data.lowest_cost;
    const bestNodes = r.found && r.nodes_explored === data.least_nodes;
    return `
      <tr class="route-row ${selectedRouteKey === r.algorithm_key ? 'selected-route-row' : ''}">
        <td><strong>${r.algorithm}</strong>${bestCost ? '<span class="mini-tag">LOWEST COST</span>' : ''}</td>
        <td>${r.found ? r.path.join(" → ") : "No route"}</td>
        <td>${r.cost ?? "-"}</td>
        <td>${r.nodes_explored}${bestNodes ? '<span class="mini-tag nodes">FEWEST NODES</span>' : ''}</td>
        <td>${r.runtime_ms}</td>
        <td><button class="route-show" onclick="showRoute('${r.algorithm_key}')">Show</button></td>
      </tr>
    `;
  }).join("");

  document.getElementById("routeTable").innerHTML = rows;

  const uniqueCosts = [...new Set(data.results.filter(r => r.found).map(r => r.cost))];
  let message;
  if (uniqueCosts.length > 1) {
    message = `Algorithms disagree. Lowest weighted route cost = <strong>${data.lowest_cost}</strong>. Cost-aware search avoids a route that is shallow or heuristically attractive but expensive.`;
  } else {
    message = `Successful algorithms found route cost <strong>${data.lowest_cost}</strong>, but with different search effort. Use <strong>Search Contrast</strong> for a clearer difference.`;
  }
  document.getElementById("routeInsight").innerHTML = message;
}

function showRoute(key) {
  selectedRouteKey = key;
  if (appState?.last_routes) renderRoutes(appState.last_routes);
  renderRadar();
}

function svgEl(name, attrs = {}, text = null) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  if (text !== null) el.textContent = text;
  return el;
}

function renderRadar() {
  if (!appState?.airspace) return;
  const svg = document.getElementById("radarSvg");
  svg.innerHTML = "";

  const W = 1000, H = 520, padX = 90, padY = 60;
  const nodes = appState.airspace.nodes;
  const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
  const xs = nodes.map(n => n.x), ys = nodes.map(n => n.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);

  const sx = x => padX + ((x - minX) / Math.max(1, maxX - minX)) * (W - 2 * padX);
  const sy = y => H - padY - ((y - minY) / Math.max(1, maxY - minY)) * (H - 2 * padY);

  const airport = nodeMap["AIRPORT"];
  const cx = sx(airport.x), cy = sy(airport.y);
  [70, 140, 210, 280].forEach(r => {
    svg.appendChild(svgEl("circle", {cx, cy, r, class: "radar-ring"}));
  });
  svg.appendChild(svgEl("line", {x1: 25, y1: cy, x2: 975, y2: cy, class: "radar-cross"}));
  svg.appendChild(svgEl("line", {x1: cx, y1: 20, x2: cx, y2: 500, class: "radar-cross"}));

  let selectedResult = null;
  if (appState.last_routes) {
    selectedResult = appState.last_routes.results.find(r => r.algorithm_key === selectedRouteKey) || null;
  }
  const selectedPairs = new Set();
  if (selectedResult?.path) {
    for (let i = 0; i < selectedResult.path.length - 1; i++) {
      selectedPairs.add([selectedResult.path[i], selectedResult.path[i+1]].sort().join("|"));
    }
  }

  appState.airspace.edges.forEach(e => {
    const a = nodeMap[e.a], b = nodeMap[e.b];
    const key = [e.a, e.b].sort().join("|");
    const active = selectedPairs.has(key);
    svg.appendChild(svgEl("line", {
      x1: sx(a.x), y1: sy(a.y), x2: sx(b.x), y2: sy(b.y),
      class: active ? "air-edge route-edge" : "air-edge"
    }));
    const mx = (sx(a.x) + sx(b.x)) / 2;
    const my = (sy(a.y) + sy(b.y)) / 2;
    svg.appendChild(svgEl("text", {x: mx + 5, y: my - 5, class: "edge-cost"}, String(e.distance)));
  });

  const runwayOpen = Object.fromEntries(appState.runways.map(r => [r.runway_id, r.is_open]));
  const runways = [
    {id: "R1", x1: cx - 115, y1: cy + 30, x2: cx - 15, y2: cy + 30},
    {id: "R2", x1: cx + 15, y1: cy + 48, x2: cx + 115, y2: cy + 48},
  ];
  runways.forEach(r => {
    svg.appendChild(svgEl("line", {
      x1: r.x1, y1: r.y1, x2: r.x2, y2: r.y2,
      class: runwayOpen[r.id] ? "runway-line runway-open" : "runway-line runway-closed"
    }));
    svg.appendChild(svgEl("text", {
      x: r.x1, y: r.y1 - 8,
      class: runwayOpen[r.id] ? "runway-label runway-label-open" : "runway-label runway-label-closed"
    }, `${r.id} ${runwayOpen[r.id] ? 'OPEN' : 'CLOSED'}`));
  });

  nodes.forEach(n => {
    const x = sx(n.x), y = sy(n.y);
    if (n.blocked) {
      svg.appendChild(svgEl("circle", {cx: x, cy: y, r: 24, class: "weather-halo"}));
      svg.appendChild(svgEl("text", {x, y: y - 30, class: "weather-icon", "text-anchor": "middle"}, "×"));
    }
    if (n.risk > 0 && !n.blocked) {
      svg.appendChild(svgEl("circle", {cx: x, cy: y, r: 18 + n.risk * 2, class: "risk-halo"}));
    }
    svg.appendChild(svgEl("circle", {
      cx: x, cy: y, r: n.id === "AIRPORT" ? 11 : 8,
      class: n.blocked ? "air-node blocked-node" : (n.id === "AIRPORT" ? "air-node airport-node" : "air-node")
    }));
    svg.appendChild(svgEl("text", {
      x, y: y - 14, class: "node-label", "text-anchor": "middle"
    }, n.id));
  });

  appState.radar_contacts.forEach(c => {
    const x = sx(c.x), y = sy(c.y);
    const g = svgEl("g", {class: `contact contact-${c.priority}`});
    const icon = svgEl("text", {x, y, class: "plane-icon", "text-anchor": "middle"}, c.operation === "arrival" ? "✈" : "➤");
    const labelText = c.route_delay > 0 ? `${c.flight_id} +${c.route_delay}m` : c.flight_id;
    const label = svgEl("text", {x: x + 13, y: y - 9, class: "contact-label"}, labelText);
    g.appendChild(icon);
    g.appendChild(label);
    svg.appendChild(g);
  });

  document.getElementById("radarScenario").textContent =
    `SCENARIO: ${appState.scenario.replaceAll('_',' ').toUpperCase()}`;

  if (selectedResult?.found) {
    document.getElementById("radarRouteLabel").textContent =
      `DISPLAYED ROUTE: ${selectedResult.algorithm} • COST ${selectedResult.cost} • ${selectedResult.path.join(' → ')}`;
  } else {
    document.getElementById("radarRouteLabel").textContent = "DISPLAYED ROUTE: NONE";
  }
}

refresh();
