from flask import Flask, jsonify, render_template, request

from core.models import Flight, minute_to_clock
from core.knowledge import infer_flight_priority, runway_knowledge
from core.scheduler import schedule_flights, compare_csp_strategies
from core.search import compare_searches
from core.scenarios import load_scenario
from core.integration import compute_route_impacts, flights_with_effective_eta
from core.explain import build_decision_traces, compute_delay_metrics
from core.validator import validate_single_runway_optimum

app = Flask(__name__)

state = {}


def reset(name="normal"):
    flights, runways, graph, blocked = load_scenario(name)
    state.clear()
    state.update({
        "scenario": name,
        "flights": flights,
        "runways": runways,
        "graph": graph,
        "blocked": blocked,
        "last_schedule": None,
        "last_routes": None,
        "last_csp_comparison": None,
        "logs": [f"Scenario loaded: {name.replace('_', ' ').title()}"],
    })


reset()


def current_route_impacts():
    return compute_route_impacts(
        state["flights"], state["graph"], state["blocked"]
    )


def radar_contacts(route_impacts):
    """Return simplified contact positions for the visual radar."""
    contacts = []
    node_counts = {}

    for flight in state["flights"]:
        node = flight.source_waypoint if flight.operation == "arrival" else "AIRPORT"
        node_counts[node] = node_counts.get(node, 0) + 1
        index = node_counts[node] - 1
        x, y = state["graph"].coords.get(node, (0, 0))

        # Larger stagger pattern than V2: improves readability around shared fixes.
        offsets = [
            (0, 0), (0.48, 0.35), (-0.48, 0.35),
            (0.62, -0.32), (-0.62, -0.32), (0, 0.62)
        ]
        dx, dy = offsets[index % len(offsets)]
        p = infer_flight_priority(flight)
        impact = route_impacts[flight.flight_id]
        contacts.append({
            "flight_id": flight.flight_id,
            "operation": flight.operation,
            "priority": p["priority"],
            "aircraft_type": flight.aircraft_type,
            "x": x + dx,
            "y": y + dy,
            "node": node,
            "route_delay": impact["route_delay"],
        })

    return contacts


def serialize_state():
    priority = {
        f.flight_id: infer_flight_priority(f)
        for f in state["flights"]
    }
    route_impacts = current_route_impacts()

    serialized_flights = []
    for f in state["flights"]:
        impact = route_impacts[f.flight_id]
        serialized_flights.append({
            **f.to_dict(),
            "base_eta": f.eta,
            "base_eta_label": minute_to_clock(f.eta),
            "effective_eta": impact["effective_eta"],
            "effective_eta_label": minute_to_clock(impact["effective_eta"]),
            "route_delay": impact["route_delay"],
            "route_status": impact["status"],
            "route_path": impact["current_path"],
            "route_cost": impact["current_cost"],
            "priority": priority[f.flight_id]["priority"],
            "inference": priority[f.flight_id]["explanations"],
        })

    return {
        "scenario": state["scenario"],
        "flights": serialized_flights,
        "runways": [r.to_dict() for r in state["runways"]],
        "blocked_waypoints": sorted(state["blocked"]),
        "last_schedule": state["last_schedule"],
        "last_routes": state["last_routes"],
        "last_csp_comparison": state["last_csp_comparison"],
        "logs": state["logs"][-30:],
        "nodes": sorted(state["graph"].edges.keys()),
        "airspace": state["graph"].to_dict(state["blocked"]),
        "radar_contacts": radar_contacts(route_impacts),
    }


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/state")
def api_state():
    return jsonify(serialize_state())


@app.post("/api/reset")
def api_reset():
    data = request.get_json(force=True)
    scenario = data.get("scenario", "normal")
    reset(scenario)
    return jsonify(serialize_state())


@app.post("/api/runway")
def api_runway():
    data = request.get_json(force=True)
    rid = data["runway_id"]
    open_flag = bool(data["is_open"])

    for r in state["runways"]:
        if r.runway_id == rid:
            r.is_open = open_flag
            state["logs"].append(
                f"{rid} set to {'OPEN' if open_flag else 'CLOSED'}."
            )
            state["last_schedule"] = None
            state["last_csp_comparison"] = None
            return jsonify(serialize_state())

    return jsonify({"error": "Unknown runway"}), 404


@app.post("/api/flight")
def api_add_flight():
    data = request.get_json(force=True)
    fid = data["flight_id"].strip().upper()

    if any(f.flight_id == fid for f in state["flights"]):
        return jsonify({"error": "Flight ID already exists."}), 400

    f = Flight(
        flight_id=fid,
        operation=data.get("operation", "arrival"),
        eta=int(data.get("eta", 0)),
        aircraft_type=data.get("aircraft_type", "medium"),
        fuel_status=data.get("fuel_status", "normal"),
        medical_emergency=bool(data.get("medical_emergency", False)),
        preferred_runway=data.get("preferred_runway", ""),
        source_waypoint=data.get("source_waypoint", "NORTH"),
    )

    state["flights"].append(f)
    state["logs"].append(f"Flight {fid} added.")
    state["last_schedule"] = None
    state["last_csp_comparison"] = None
    return jsonify(serialize_state())


@app.post("/api/emergency")
def api_emergency():
    data = request.get_json(force=True)
    fid = data["flight_id"]

    for f in state["flights"]:
        if f.flight_id == fid:
            f.fuel_status = data.get("fuel_status", "critical")
            f.medical_emergency = bool(
                data.get("medical_emergency", f.medical_emergency)
            )
            state["logs"].append(
                f"Emergency update received for {fid}: fuel={f.fuel_status}."
            )
            state["last_schedule"] = None
            state["last_csp_comparison"] = None
            return jsonify(serialize_state())

    return jsonify({"error": "Flight not found"}), 404


@app.post("/api/weather")
def api_weather():
    data = request.get_json(force=True)
    node = data["node"]
    blocked = bool(data.get("blocked", True))

    if node not in state["graph"].edges:
        return jsonify({"error": "Unknown waypoint"}), 404

    if blocked:
        state["blocked"].add(node)
        state["logs"].append(f"Severe weather blocked waypoint {node}.")
    else:
        state["blocked"].discard(node)
        state["logs"].append(f"Waypoint {node} reopened.")

    state["last_routes"] = None
    state["last_schedule"] = None
    state["last_csp_comparison"] = None
    return jsonify(serialize_state())


@app.post("/api/schedule")
def api_schedule():
    priority_map = {
        f.flight_id: infer_flight_priority(f)
        for f in state["flights"]
    }

    route_impacts = current_route_impacts()
    adjusted_flights = flights_with_effective_eta(
        state["flights"], route_impacts
    )

    result = schedule_flights(
        adjusted_flights,
        state["runways"],
        priority_map,
    )

    # Independent exact validation is intentionally separate from the AI/CSP
    # optimizer. For small one-runway cases it checks every possible flight
    # ordering and confirms the global weighted-delay optimum.
    validation = validate_single_runway_optimum(
        adjusted_flights, state["runways"], priority_map
    )
    if validation.get("available") and result.get("solved"):
        validation["matches_optimizer"] = (
            validation["best_weighted_cost"]
            == result["stats"].get("best_weighted_cost")
        )
    result["exact_validation"] = validation

    runway_info = runway_knowledge(state["runways"])
    explanations = {}

    if result["solved"]:
        # Enrich schedule rows with the route-planning contribution so the UI
        # can separate search-induced ETA shift from CSP-induced runway delay.
        for a in result["assignments"]:
            impact = route_impacts[a["flight_id"]]
            original = next(f for f in state["flights"] if f.flight_id == a["flight_id"])
            a["planned_eta"] = original.eta
            a["planned_eta_label"] = minute_to_clock(original.eta)
            a["route_delay"] = impact["route_delay"]
            a["effective_eta"] = impact["effective_eta"]
            a["effective_eta_label"] = minute_to_clock(impact["effective_eta"])
            a["total_delay_from_planned"] = impact["route_delay"] + a["delay"]

        by_id_original = {f.flight_id: f for f in state["flights"]}
        by_id_adjusted = {f.flight_id: f for f in adjusted_flights}

        for a in result["assignments"]:
            fid = a["flight_id"]
            original = by_id_original[fid]
            adjusted = by_id_adjusted[fid]
            impact = route_impacts[fid]
            reasons = list(priority_map[fid]["explanations"])

            if impact["route_delay"] > 0:
                path = " → ".join(impact["current_path"]) or "No route"
                reasons.append(
                    f"A* route conditions added {impact['route_delay']} minute(s) "
                    f"to ETA; effective ETA became {minute_to_clock(adjusted.eta)}."
                )
                reasons.append(f"Current arrival route: {path}.")

            if not all(r.is_open for r in state["runways"]):
                reasons.append(
                    "Closed runways were removed from the CSP domain."
                )

            if a["delay"] == 0:
                reasons.append(
                    "The optimizer found a conflict-free slot at the effective ETA."
                )
            else:
                reasons.append(
                    f"The flight was delayed by {a['delay']} minute(s) beyond its "
                    "effective ETA to maintain runway separation constraints."
                )

            reasons.append(
                f"Its priority-weighted delay contribution is {a['weighted_delay']}."
            )
            reasons.append(
                f"{a['runway_id']} at {a['slot_label']} is part of the minimum-cost "
                "schedule found by the branch-and-bound CSP optimizer."
            )
            explanations[fid] = reasons

    # V5 presentation metrics separate route delay from scheduler delay.
    if result.get("solved"):
        assignments = result.get("assignments", [])
        result["stats"].update(compute_delay_metrics(assignments))

        result["decision_traces"] = build_decision_traces(
            state["flights"],
            state["runways"],
            state["blocked"],
            priority_map,
            route_impacts,
            result,
        )
    else:
        result["decision_traces"] = {}

    result["explanations"] = explanations
    result["knowledge"] = runway_info
    result["route_impacts"] = route_impacts
    state["last_schedule"] = result
    state["logs"].append(
        "Optimizing CSP scheduler executed successfully."
        if result["solved"]
        else "Optimizing CSP scheduler could not find a valid schedule."
    )
    return jsonify(result)


@app.post("/api/csp-compare")
def api_csp_compare():
    priority_map = {
        f.flight_id: infer_flight_priority(f)
        for f in state["flights"]
    }
    route_impacts = current_route_impacts()
    adjusted_flights = flights_with_effective_eta(
        state["flights"], route_impacts
    )
    results = compare_csp_strategies(
        adjusted_flights,
        state["runways"],
        priority_map,
    )
    payload = {"results": results}
    state["last_csp_comparison"] = payload
    state["logs"].append(
        "Compared Plain Backtracking, MRV and MRV + Forward Checking."
    )
    return jsonify(payload)


@app.post("/api/routes")
def api_routes():
    data = request.get_json(force=True)
    start = data.get("start", "NORTH")
    goal = data.get("goal", "AIRPORT")

    if start not in state["graph"].edges or goal not in state["graph"].edges:
        return jsonify({"error": "Unknown start/goal node."}), 400

    results = compare_searches(
        state["graph"],
        start,
        goal,
        state["blocked"],
    )

    valid = [r for r in results if r["found"] and r["cost"] is not None]
    lowest_cost = min((r["cost"] for r in valid), default=None)
    least_nodes = min((r["nodes_explored"] for r in valid), default=None)

    payload = {
        "start": start,
        "goal": goal,
        "blocked": sorted(state["blocked"]),
        "results": results,
        "lowest_cost": lowest_cost,
        "least_nodes": least_nodes,
    }
    state["last_routes"] = payload

    state["logs"].append(
        f"Compared BFS/UCS/Greedy/A* from {start} to {goal}."
    )
    return jsonify(payload)


if __name__ == "__main__":
    app.run(debug=True)
