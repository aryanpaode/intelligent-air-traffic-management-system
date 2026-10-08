import math
from copy import deepcopy

from .search import run_search
from .scenarios import base_graph


ROUTE_COST_PER_DELAY_MINUTE = 3.0


def route_impact_for_flight(flight, current_graph, blocked):
    """
    Convert route disruption into a small simulated ETA shift.

    Baseline and current routes are both chosen with A*. Any increase in
    weighted route cost becomes a route-induced ETA delay. This intentionally
    simplified conversion exists to connect the search subsystem to the CSP.
    """
    if flight.operation != "arrival" or flight.source_waypoint == "AIRPORT":
        return {
            "baseline_cost": 0,
            "current_cost": 0,
            "route_delay": 0,
            "effective_eta": flight.eta,
            "baseline_path": [],
            "current_path": [],
            "status": "not_applicable",
        }

    baseline_graph = base_graph()
    baseline = run_search(
        baseline_graph,
        "astar",
        flight.source_waypoint,
        "AIRPORT",
        set(),
    )
    current = run_search(
        current_graph,
        "astar",
        flight.source_waypoint,
        "AIRPORT",
        blocked,
    )

    if not current["found"]:
        return {
            "baseline_cost": baseline["cost"],
            "current_cost": None,
            "route_delay": 20,
            "effective_eta": flight.eta + 20,
            "baseline_path": baseline["path"],
            "current_path": [],
            "status": "no_route",
        }

    baseline_cost = baseline["cost"] or 0
    current_cost = current["cost"] or baseline_cost
    extra = max(0.0, current_cost - baseline_cost)
    route_delay = int(math.ceil(extra / ROUTE_COST_PER_DELAY_MINUTE)) if extra else 0

    return {
        "baseline_cost": baseline_cost,
        "current_cost": current_cost,
        "route_delay": route_delay,
        "effective_eta": flight.eta + route_delay,
        "baseline_path": baseline["path"],
        "current_path": current["path"],
        "status": "rerouted" if route_delay > 0 or current["path"] != baseline["path"] else "normal",
    }


def compute_route_impacts(flights, graph, blocked):
    return {
        f.flight_id: route_impact_for_flight(f, graph, blocked)
        for f in flights
    }


def flights_with_effective_eta(flights, route_impacts):
    """Return copies so the user's baseline ETA is never overwritten."""
    adjusted = []
    for f in flights:
        clone = deepcopy(f)
        clone.eta = route_impacts[f.flight_id]["effective_eta"]
        adjusted.append(clone)
    return adjusted
