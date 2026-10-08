from dataclasses import dataclass
from time import perf_counter
from .models import minute_to_clock


PRIORITY_WEIGHTS = {
    "normal": 1,
    "high": 3,
    "emergency": 10,
}


@dataclass
class Assignment:
    flight_id: str
    runway_id: str
    slot: int
    priority: str
    delay: int
    weighted_delay: int

    def to_dict(self):
        return {
            "flight_id": self.flight_id,
            "runway_id": self.runway_id,
            "slot": self.slot,
            "slot_label": minute_to_clock(self.slot),
            "priority": self.priority,
            "delay": self.delay,
            "weighted_delay": self.weighted_delay,
        }


def separation_minutes(flight_a, flight_b):
    """
    Simplified academic wake/separation model.
    This is NOT an operational aviation standard.
    """
    sep = {"light": 3, "medium": 4, "heavy": 5}
    return max(
        sep.get(flight_a.aircraft_type, 4),
        sep.get(flight_b.aircraft_type, 4),
    )


def build_domain(flight, runways, priority_info, horizon=28):
    """Create candidate (runway, time) values for one CSP variable."""
    values = []
    priority = priority_info["priority"]
    weight = PRIORITY_WEIGHTS[priority]

    for runway in runways:
        if not runway.is_open:
            continue
        if flight.aircraft_type not in runway.allowed_types:
            continue

        for t in range(flight.eta, flight.eta + horizon + 1):
            delay = t - flight.eta
            pref_penalty = (
                0
                if not flight.preferred_runway
                or flight.preferred_runway == runway.runway_id
                else 1
            )
            objective = delay * weight + pref_penalty
            values.append((objective, delay, runway.runway_id, t))

    values.sort(key=lambda x: (x[0], x[1], x[3], x[2]))
    return [(runway, t) for _, _, runway, t in values]


def is_consistent(flight, runway_id, slot, assignments, flights_by_id, stats=None):
    for other_id, other in assignments.items():
        if stats is not None:
            stats["constraint_checks"] += 1
        if other.runway_id != runway_id:
            continue

        other_flight = flights_by_id[other_id]
        sep = separation_minutes(flight, other_flight)
        if abs(slot - other.slot) < sep:
            return False

    return True


def _assignment_cost(flight, slot, priority):
    delay = slot - flight.eta
    return delay * PRIORITY_WEIGHTS[priority]


def _ordered_values(flight, domain, priority, runway_preference=True):
    weight = PRIORITY_WEIGHTS[priority]

    def key(rv):
        runway_id, slot = rv
        delay = slot - flight.eta
        pref = 0
        if runway_preference and flight.preferred_runway:
            pref = 0 if flight.preferred_runway == runway_id else 1
        return (delay * weight + pref, delay, slot, runway_id)

    return sorted(domain, key=key)


def _initial_greedy_solution(flights, domains, priority_map, flights_by_id):
    """Fast incumbent used by branch-and-bound to prune aggressively."""
    assignments = {}
    ordered = sorted(
        flights,
        key=lambda f: (
            priority_map[f.flight_id]["priority_rank"],
            f.eta,
            f.flight_id,
        ),
    )

    for flight in ordered:
        values = _ordered_values(
            flight,
            domains[flight.flight_id],
            priority_map[flight.flight_id]["priority"],
        )
        chosen = None
        for runway_id, slot in values:
            if is_consistent(flight, runway_id, slot, assignments, flights_by_id):
                chosen = (runway_id, slot)
                break
        if chosen is None:
            return None
        runway_id, slot = chosen
        priority = priority_map[flight.flight_id]["priority"]
        delay = slot - flight.eta
        assignments[flight.flight_id] = Assignment(
            flight.flight_id,
            runway_id,
            slot,
            priority,
            delay,
            delay * PRIORITY_WEIGHTS[priority],
        )

    return assignments


def _initial_unbounded_greedy_solution(flights, runways, priority_map, flights_by_id):
    """Build a feasible incumbent without imposing an arbitrary time horizon.

    Flights are considered in priority/ETA order. For each compatible open
    runway, the earliest conflict-free slot is found by scanning forward from
    the effective ETA. Because only finitely many flights are already assigned,
    a conflict-free future slot must eventually exist on a compatible runway.
    """
    assignments = {}
    ordered = sorted(
        flights,
        key=lambda f: (
            priority_map[f.flight_id]["priority_rank"],
            f.eta,
            f.flight_id,
        ),
    )

    for flight in ordered:
        priority = priority_map[flight.flight_id]["priority"]
        weight = PRIORITY_WEIGHTS[priority]
        options = []

        for runway in runways:
            if not runway.is_open:
                continue
            if flight.aircraft_type not in runway.allowed_types:
                continue

            slot = flight.eta
            while not is_consistent(
                flight,
                runway.runway_id,
                slot,
                assignments,
                flights_by_id,
            ):
                slot += 1

            delay = slot - flight.eta
            pref_penalty = (
                0
                if not flight.preferred_runway
                or flight.preferred_runway == runway.runway_id
                else 1
            )
            options.append(
                (delay * weight + pref_penalty, delay, slot, runway.runway_id)
            )

        if not options:
            return None

        options.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        _, delay, slot, runway_id = options[0]
        assignments[flight.flight_id] = Assignment(
            flight.flight_id,
            runway_id,
            slot,
            priority,
            delay,
            delay * weight,
        )

    return assignments


def _objective_bounded_domain(flight, runways, priority_info, incumbent_cost):
    """Return every value that could strictly improve the current incumbent.

    All objective terms are non-negative. If the incumbent has cost B, any
    single flight assignment whose weighted delay is >= B cannot belong to a
    schedule with total cost < B. Therefore the search can be finite without a
    fixed scheduling horizon.
    """
    priority = priority_info["priority"]
    weight = PRIORITY_WEIGHTS[priority]

    if incumbent_cost <= 0:
        max_delay = 0
    else:
        max_delay = (int(incumbent_cost) - 1) // weight

    values = []
    for runway in runways:
        if not runway.is_open:
            continue
        if flight.aircraft_type not in runway.allowed_types:
            continue

        for t in range(flight.eta, flight.eta + max_delay + 1):
            delay = t - flight.eta
            pref_penalty = (
                0
                if not flight.preferred_runway
                or flight.preferred_runway == runway.runway_id
                else 1
            )
            ordering_score = delay * weight + pref_penalty
            values.append((ordering_score, delay, runway.runway_id, t))

    values.sort(key=lambda x: (x[0], x[1], x[3], x[2]))
    return [(runway, t) for _, _, runway, t in values]


def schedule_flights(flights, runways, priority_map):
    """Exact priority-weighted CSP optimizer with no fixed scheduling horizon.

    Objective:
        minimize sum(delay_i * priority_weight_i)

    Search techniques:
        - backtracking
        - MRV variable ordering
        - least-cost value ordering
        - forward checking / constraint propagation
        - branch-and-bound using a lower bound
        - objective-derived finite domains

    Exactness of the domain bound:
        A feasible incumbent of cost B is constructed first. Since every delay
        contribution is non-negative, a candidate value with weighted delay
        >= B cannot be part of any schedule whose total cost is strictly less
        than B. This removes the previous arbitrary +20 minute cutoff while
        keeping the search finite.
    """
    start = perf_counter()
    flights_by_id = {f.flight_id: f for f in flights}

    incumbent = _initial_unbounded_greedy_solution(
        flights, runways, priority_map, flights_by_id
    )

    stats = {
        "variables": len(flights),
        "candidate_assignments": 0,
        "constraint_checks": 0,
        "backtracks": 0,
        "complete_schedules": 0,
        "branches_pruned": 0,
        "forward_checks": 0,
        "fixed_horizon_used": False,
        "domain_bound_method": "objective_bound_from_feasible_incumbent",
    }

    if incumbent is None:
        stats["runtime_ms"] = round((perf_counter() - start) * 1000, 3)
        return {
            "solved": False,
            "assignments": [],
            "stats": stats,
            "message": "At least one flight has no compatible open runway.",
        }

    best_assignments = dict(incumbent)
    best_cost = sum(a.weighted_delay for a in incumbent.values())
    stats["initial_incumbent_cost"] = best_cost

    # A zero-cost feasible schedule is already globally optimal.
    if best_cost == 0:
        ordered = sorted(
            best_assignments.values(),
            key=lambda a: (a.slot, a.runway_id, a.flight_id),
        )
        stats["best_weighted_cost"] = 0
        stats["total_delay"] = 0
        stats["average_delay"] = 0
        stats["emergency_delay"] = 0
        stats["runtime_ms"] = round((perf_counter() - start) * 1000, 3)
        return {
            "solved": True,
            "assignments": [a.to_dict() for a in ordered],
            "stats": stats,
            "objective": {
                "name": "priority_weighted_delay",
                "weights": PRIORITY_WEIGHTS,
                "value": 0,
            },
            "message": "Zero-delay schedule is globally optimal.",
        }

    domains = {
        f.flight_id: _objective_bounded_domain(
            f, runways, priority_map[f.flight_id], best_cost
        )
        for f in flights
    }

    if any(len(domains[f.flight_id]) == 0 for f in flights):
        stats["runtime_ms"] = round((perf_counter() - start) * 1000, 3)
        return {
            "solved": False,
            "assignments": [],
            "stats": stats,
            "message": "At least one flight has no legal runway/time values.",
        }

    assignments = {}

    def valid_values(flight, remaining_budget=None):
        vals = []
        priority = priority_map[flight.flight_id]["priority"]
        for runway_id, slot in domains[flight.flight_id]:
            inc_cost = _assignment_cost(flight, slot, priority)
            if remaining_budget is not None and inc_cost >= remaining_budget:
                continue
            stats["candidate_assignments"] += 1
            if is_consistent(
                flight,
                runway_id,
                slot,
                assignments,
                flights_by_id,
                stats,
            ):
                vals.append((runway_id, slot))
        return vals

    def remaining_info(current_cost):
        candidates = []
        lower_bound_add = 0

        for f in flights:
            if f.flight_id in assignments:
                continue

            budget = best_cost - current_cost
            vv = valid_values(f, budget)
            stats["forward_checks"] += 1
            if not vv:
                return None, None, None

            priority = priority_map[f.flight_id]["priority"]
            vv = _ordered_values(f, vv, priority)
            _, cheapest_slot = vv[0]
            lower_bound_add += _assignment_cost(f, cheapest_slot, priority)
            candidates.append(
                (
                    len(vv),
                    priority_map[f.flight_id]["priority_rank"],
                    f.eta,
                    f.flight_id,
                    f,
                    vv,
                )
            )

        if not candidates:
            return None, [], lower_bound_add

        candidates.sort(key=lambda x: (x[0], x[1], x[2], x[3]))
        chosen = candidates[0]
        return chosen[4], chosen[5], lower_bound_add

    def recurse(current_cost):
        nonlocal best_assignments, best_cost

        if len(assignments) == len(flights):
            stats["complete_schedules"] += 1
            if current_cost < best_cost:
                best_cost = current_cost
                best_assignments = dict(assignments)
            return

        flight, values, lower_add = remaining_info(current_cost)
        if values is None:
            stats["backtracks"] += 1
            return

        if current_cost + lower_add >= best_cost:
            stats["branches_pruned"] += 1
            return

        if flight is None:
            return

        priority = priority_map[flight.flight_id]["priority"]
        weight = PRIORITY_WEIGHTS[priority]

        for runway_id, slot in values:
            delay = slot - flight.eta
            inc_cost = delay * weight
            next_cost = current_cost + inc_cost
            if next_cost >= best_cost:
                stats["branches_pruned"] += 1
                continue

            assignments[flight.flight_id] = Assignment(
                flight.flight_id,
                runway_id,
                slot,
                priority,
                delay,
                inc_cost,
            )
            recurse(next_cost)
            assignments.pop(flight.flight_id, None)

        stats["backtracks"] += 1

    recurse(0)
    stats["runtime_ms"] = round((perf_counter() - start) * 1000, 3)
    stats["best_weighted_cost"] = best_cost

    ordered = sorted(
        best_assignments.values(),
        key=lambda a: (a.slot, a.runway_id, a.flight_id),
    )
    total_delay = sum(a.delay for a in ordered)
    emergency_delay = sum(
        a.delay for a in ordered if a.priority == "emergency"
    )

    stats["total_delay"] = total_delay
    stats["average_delay"] = round(total_delay / len(ordered), 2) if ordered else 0
    stats["emergency_delay"] = emergency_delay

    return {
        "solved": True,
        "assignments": [a.to_dict() for a in ordered],
        "stats": stats,
        "objective": {
            "name": "priority_weighted_delay",
            "weights": PRIORITY_WEIGHTS,
            "value": best_cost,
        },
        "message": (
            "Globally optimized conflict-free schedule generated with "
            "objective-bounded branch-and-bound, MRV and forward checking."
        ),
    }

def _first_feasible(flights, runways, priority_map, strategy="plain", horizon=20):
    """Fast first-solution solver used only for heuristic comparison statistics."""
    start = perf_counter()
    flights_by_id = {f.flight_id: f for f in flights}
    domains = {
        f.flight_id: build_domain(f, runways, priority_map[f.flight_id], horizon)
        for f in flights
    }
    assignments = {}
    stats = {
        "candidate_assignments": 0,
        "constraint_checks": 0,
        "backtracks": 0,
        "forward_checks": 0,
    }

    fixed_order = sorted(
        flights,
        key=lambda f: (
            priority_map[f.flight_id]["priority_rank"],
            f.eta,
            f.flight_id,
        ),
    )

    def valid_values(f):
        vals = []
        for runway_id, slot in domains[f.flight_id]:
            stats["candidate_assignments"] += 1
            if is_consistent(
                f, runway_id, slot, assignments, flights_by_id, stats
            ):
                vals.append((runway_id, slot))
        return _ordered_values(f, vals, priority_map[f.flight_id]["priority"])

    def choose():
        remaining = [f for f in fixed_order if f.flight_id not in assignments]
        if not remaining:
            return None, []

        if strategy == "plain":
            f = remaining[0]
            return f, valid_values(f)

        candidates = []
        for f in remaining:
            vv = valid_values(f)
            if strategy == "mrv_fc":
                stats["forward_checks"] += 1
                if not vv:
                    return f, []
            candidates.append((len(vv), f.eta, f.flight_id, f, vv))
        candidates.sort(key=lambda x: (x[0], x[1], x[2]))
        return candidates[0][3], candidates[0][4]

    def recurse():
        if len(assignments) == len(flights):
            return True

        f, values = choose()
        if f is None:
            return True
        if not values:
            stats["backtracks"] += 1
            return False

        for runway_id, slot in values:
            delay = slot - f.eta
            p = priority_map[f.flight_id]["priority"]
            assignments[f.flight_id] = Assignment(
                f.flight_id,
                runway_id,
                slot,
                p,
                delay,
                delay * PRIORITY_WEIGHTS[p],
            )

            if strategy == "mrv_fc":
                impossible = False
                for other in flights:
                    if other.flight_id in assignments:
                        continue
                    stats["forward_checks"] += 1
                    if not valid_values(other):
                        impossible = True
                        break
                if impossible:
                    assignments.pop(f.flight_id, None)
                    continue

            if recurse():
                return True
            assignments.pop(f.flight_id, None)

        stats["backtracks"] += 1
        return False

    solved = recurse()
    stats["runtime_ms"] = round((perf_counter() - start) * 1000, 3)
    return {
        "strategy": strategy,
        "solved": solved,
        "stats": stats,
    }


def compare_csp_strategies(flights, runways, priority_map):
    labels = {
        "plain": "Plain Backtracking",
        "mrv": "Backtracking + MRV",
        "mrv_fc": "MRV + Forward Checking",
    }
    results = []
    for key in ("plain", "mrv", "mrv_fc"):
        r = _first_feasible(flights, runways, priority_map, key)
        r["label"] = labels[key]
        results.append(r)
    return results
