"""Independent exact validator for small single-runway scenarios.

This module is intentionally separate from the CSP optimizer. For at most eight
flights and exactly one open compatible runway, it evaluates every possible
flight ordering (n!) and schedules each ordering as early as the separation and
effective-time constraints allow. It is used only to verify the optimizer.
"""

from itertools import permutations
from time import perf_counter

from .scheduler import PRIORITY_WEIGHTS, separation_minutes


def validate_single_runway_optimum(flights, runways, priority_map, max_flights=8):
    open_runways = [r for r in runways if r.is_open]
    if len(open_runways) != 1:
        return {
            "available": False,
            "reason": "Exact permutation validation requires exactly one open runway.",
        }

    if len(flights) > max_flights:
        return {
            "available": False,
            "reason": f"Exact permutation validation is limited to {max_flights} flights.",
        }

    runway = open_runways[0]
    if any(f.aircraft_type not in runway.allowed_types for f in flights):
        return {
            "available": False,
            "reason": "At least one flight is incompatible with the single open runway.",
        }

    start = perf_counter()
    by_id = {f.flight_id: f for f in flights}
    ids = [f.flight_id for f in flights]

    best_cost = float("inf")
    best_order = None
    best_schedule = None
    permutations_checked = 0

    for order in permutations(ids):
        permutations_checked += 1
        previous_flight = None
        previous_slot = None
        cost = 0
        schedule = []

        for fid in order:
            flight = by_id[fid]
            if previous_flight is None:
                slot = flight.eta
            else:
                slot = max(
                    flight.eta,
                    previous_slot + separation_minutes(previous_flight, flight),
                )

            delay = slot - flight.eta
            priority = priority_map[fid]["priority"]
            weighted = delay * PRIORITY_WEIGHTS[priority]
            cost += weighted

            # No continuation of this ordering can beat the incumbent because
            # all remaining delay contributions are non-negative.
            if cost >= best_cost:
                break

            schedule.append({
                "flight_id": fid,
                "slot": slot,
                "delay": delay,
                "priority": priority,
                "weighted_delay": weighted,
            })
            previous_flight = flight
            previous_slot = slot
        else:
            if cost < best_cost:
                best_cost = cost
                best_order = list(order)
                best_schedule = schedule

    return {
        "available": True,
        "runway_id": runway.runway_id,
        "permutations_checked": permutations_checked,
        "best_weighted_cost": int(best_cost),
        "best_order": best_order,
        "best_schedule": best_schedule,
        "runtime_ms": round((perf_counter() - start) * 1000, 3),
    }
