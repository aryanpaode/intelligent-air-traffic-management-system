"""Structured, deterministic explanations for the V5 decision-trace UI."""

from .models import minute_to_clock
from .scheduler import PRIORITY_WEIGHTS


def compute_delay_metrics(assignments):
    """Return presentation metrics that keep route and CSP delay distinct."""
    if not assignments:
        return {
            "average_route_delay": 0,
            "average_total_delay": 0,
            "emergency_total_delay": 0,
        }

    route_delays = [a.get("route_delay", 0) for a in assignments]
    total_delays = [
        a.get("route_delay", 0) + a.get("delay", 0)
        for a in assignments
    ]
    emergency_total = sum(
        a.get("route_delay", 0) + a.get("delay", 0)
        for a in assignments
        if a.get("priority") == "emergency"
    )
    return {
        "average_route_delay": round(sum(route_delays) / len(assignments), 2),
        "average_total_delay": round(sum(total_delays) / len(assignments), 2),
        "emergency_total_delay": emergency_total,
    }


def _path_text(path):
    return " → ".join(path) if path else "No route"


def build_decision_traces(
    original_flights,
    runways,
    blocked,
    priority_map,
    route_impacts,
    schedule_result,
):
    """
    Build one end-to-end trace per scheduled flight.

    The trace deliberately mirrors the project architecture:
    observed facts -> forward chaining -> A* route assessment -> CSP domain ->
    branch-and-bound optimization -> final decision.
    """
    if not schedule_result.get("solved"):
        return {}

    original_by_id = {f.flight_id: f for f in original_flights}
    open_runways = [r.runway_id for r in runways if r.is_open]
    closed_runways = [r.runway_id for r in runways if not r.is_open]
    global_cost = schedule_result.get("stats", {}).get("best_weighted_cost")
    branches_pruned = schedule_result.get("stats", {}).get("branches_pruned", 0)

    traces = {}

    for assignment in schedule_result["assignments"]:
        fid = assignment["flight_id"]
        flight = original_by_id[fid]
        priority_info = priority_map[fid]
        impact = route_impacts[fid]
        priority = priority_info["priority"]
        weight = PRIORITY_WEIGHTS[priority]

        eligible_runways = [
            r.runway_id
            for r in runways
            if r.is_open and flight.aircraft_type in r.allowed_types
        ]

        fact_items = [
            f"Flight {fid}: {flight.operation}, {flight.aircraft_type} aircraft.",
            f"Planned ETA = {minute_to_clock(flight.eta)}.",
            f"Fuel status = {flight.fuel_status}.",
            f"Source/position = {flight.source_waypoint}.",
        ]
        if flight.medical_emergency:
            fact_items.append("Medical emergency fact = true.")

        rule_items = []
        for rule in priority_info.get("rules_fired", []):
            rule_items.append(
                f"{rule['rule_id']}: IF {rule['condition']} THEN {rule['conclusion']}."
            )
        rule_items.append(
            f"Inferred scheduling priority = {priority.upper()} (objective weight ×{weight})."
        )

        if flight.operation == "arrival" and flight.source_waypoint != "AIRPORT":
            route_items = [
                f"Baseline A* route: {_path_text(impact['baseline_path'])} (cost {impact['baseline_cost']}).",
                f"Current A* route: {_path_text(impact['current_path'])} (cost {impact['current_cost']}).",
            ]
            if blocked:
                route_items.append(
                    f"Blocked waypoint(s): {', '.join(sorted(blocked))}."
                )
            else:
                route_items.append("No waypoint is currently blocked.")
            route_items.extend([
                f"Route-induced delay = +{impact['route_delay']} min.",
                f"Effective ETA supplied to the CSP = {minute_to_clock(impact['effective_eta'])}.",
            ])
        else:
            route_items = [
                "A* arrival-route adjustment is not applicable to this departure.",
                f"Effective scheduling time remains {minute_to_clock(impact['effective_eta'])}.",
            ]

        domain_items = [
            f"Open runways = {', '.join(open_runways) if open_runways else 'none'}.",
            f"Legal runway domain for this aircraft = {', '.join(eligible_runways) if eligible_runways else 'none'}.",
            f"Earliest legal scheduling time = effective ETA {minute_to_clock(impact['effective_eta'])}.",
            "Runway-time values that violate the simplified separation constraint are rejected.",
        ]
        if closed_runways:
            domain_items.append(
                f"Closed runway(s) removed from the domain: {', '.join(closed_runways)}."
            )

        optimization_items = [
            "Branch-and-bound searches feasible schedules while MRV selects constrained flights and forward checking removes impossible future values.",
            f"Selected assignment = {assignment['runway_id']} at {assignment['slot_label']}.",
            f"CSP delay beyond effective ETA = +{assignment['delay']} min.",
            f"Flight contribution to objective = {assignment['delay']} × {weight} = {assignment['weighted_delay']}.",
            f"Best global priority-weighted CSP cost found = {global_cost}.",
            f"Global branch-and-bound search pruned {branches_pruned} branch(es).",
        ]

        total_delay = impact["route_delay"] + assignment["delay"]
        final_items = [
            f"Final decision: {fid} → {assignment['runway_id']} at {assignment['slot_label']}.",
            f"Delay decomposition: route +{impact['route_delay']} min + CSP +{assignment['delay']} min = total +{total_delay} min.",
            f"The final slot is not earlier than the effective ETA ({minute_to_clock(impact['effective_eta'])}).",
        ]

        traces[fid] = {
            "flight_id": fid,
            "priority": priority,
            "summary": (
                f"{fid} is assigned to {assignment['runway_id']} at {assignment['slot_label']} "
                f"with {total_delay} minute(s) total delay."
            ),
            "stages": [
                {"code": "01", "title": "Observed Facts", "tone": "facts", "items": fact_items},
                {"code": "02", "title": "Forward Chaining", "tone": "inference", "items": rule_items},
                {"code": "03", "title": "A* Route Assessment", "tone": "search", "items": route_items},
                {"code": "04", "title": "CSP Domain & Constraints", "tone": "constraint", "items": domain_items},
                {"code": "05", "title": "Priority-Weighted Optimization", "tone": "optimization", "items": optimization_items},
                {"code": "06", "title": "Final Decision", "tone": "final", "items": final_items},
            ],
        }

    return traces
