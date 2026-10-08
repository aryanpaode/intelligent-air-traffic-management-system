"""Reproduce the V5 eight-flight combined-disruption result from original source.

Run: python reproduce_combined_case.py

This script is a thin independent invocation of the project's core modules,
not a change to their scheduling/inference/search algorithms. It also runs
the built-in exact one-runway permutation validator.
"""

from core.scenarios import load_scenario
from core.knowledge import infer_flight_priority
from core.integration import compute_route_impacts, flights_with_effective_eta
from core.scheduler import schedule_flights
from core.validator import validate_single_runway_optimum
from core.models import minute_to_clock


def main():
    flights, runways, graph, blocked = load_scenario("combined")
    priority_map = {f.flight_id: infer_flight_priority(f) for f in flights}
    route_impacts = compute_route_impacts(flights, graph, blocked)
    adjusted = flights_with_effective_eta(flights, route_impacts)
    optimized = schedule_flights(adjusted, runways, priority_map)
    exact = validate_single_runway_optimum(adjusted, runways, priority_map)

    target = next(f for f in flights if f.flight_id == "AI222")
    impact = route_impacts[target.flight_id]
    ai_row = next(a for a in optimized["assignments"] if a["flight_id"] == "AI222")
    assignments = sorted(optimized["assignments"], key=lambda a: (a["slot"], a["flight_id"]))

    assert optimized["solved"]
    assert len(assignments) == len(flights) == 8
    assert set(blocked) == {"WP1"}
    assert [r.runway_id for r in runways if r.is_open] == ["R1"]
    assert priority_map["AI222"]["priority"] == "emergency"
    assert impact["baseline_cost"] == 12.5
    assert impact["current_cost"] == 22.5
    assert impact["route_delay"] == 4
    assert impact["effective_eta"] == 13
    assert optimized["stats"]["best_weighted_cost"] == 77
    assert ai_row["runway_id"] == "R1"
    assert ai_row["slot"] == 13 and ai_row["delay"] == 0
    assert exact["available"] is True
    assert exact["permutations_checked"] == 40320
    assert exact["best_weighted_cost"] == 77

    print("Intelligent Air Traffic Management System — V5")
    print("CASE: Combined Disruption")
    print("Open runway(s): R1 | Closed runway(s): R2 | Blocked waypoint: WP1")
    print("Flight: AI222 | Fuel: critical | Inferred priority: emergency (weight 10)")
    print("Baseline route: " + " -> ".join(impact["baseline_path"]))
    print("Baseline route cost: 12.5")
    print("Disrupted route: " + " -> ".join(impact["current_path"]))
    print("Disrupted route cost: 22.5")
    print("Route-induced delay: 4 min | Planned ETA: 10:09 | Effective ETA: 10:13")
    print("")
    print("OPTIMAL RUNWAY SCHEDULE (one optimal order)")
    print("Flight   Effective   Scheduled   CSP delay   Penalty")
    by_id = {f.flight_id: f for f in adjusted}
    for a in assignments:
        print(f"{a['flight_id']:<8} {minute_to_clock(by_id[a['flight_id']].eta):<11} "
              f"{minute_to_clock(a['slot']):<11} {a['delay']:<11} {a['weighted_delay']}")
    print("")
    print(f"Priority-weighted scheduler score: {optimized['stats']['best_weighted_cost']}")
    print("AI222 assigned R1 at 10:13, with 0 min scheduler delay and 4 min total delay")
    print(f"Exact single-runway permutation check: {exact['permutations_checked']:,} orderings; "
          f"minimum score {exact['best_weighted_cost']}")
    print("ALL CHECKS PASSED")


if __name__ == '__main__':
    main()
