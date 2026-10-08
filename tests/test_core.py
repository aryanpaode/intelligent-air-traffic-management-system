from core.scenarios import load_scenario
from core.knowledge import infer_flight_priority
from core.scheduler import schedule_flights, compare_csp_strategies
from core.search import compare_searches
from core.integration import compute_route_impacts, flights_with_effective_eta


def prep(name):
    flights, runways, graph, blocked = load_scenario(name)
    priorities = {f.flight_id: infer_flight_priority(f) for f in flights}
    impacts = compute_route_impacts(flights, graph, blocked)
    adjusted = flights_with_effective_eta(flights, impacts)
    return flights, adjusted, runways, graph, blocked, priorities, impacts


def test_emergency_inference():
    flights, _, _, _, _, _, _ = prep("emergency")
    target = [f for f in flights if f.flight_id == "AI222"][0]
    info = infer_flight_priority(target)
    assert info["priority"] == "emergency"


def test_normal_optimized_schedule_solves():
    _, adjusted, runways, _, _, priorities, _ = prep("normal")
    result = schedule_flights(adjusted, runways, priorities)
    assert result["solved"]
    assert len(result["assignments"]) == len(adjusted)
    assert result["objective"]["name"] == "priority_weighted_delay"
    assert result["stats"]["best_weighted_cost"] == sum(
        a["weighted_delay"] for a in result["assignments"]
    )


def test_runway_closure_still_solves_on_r1():
    _, adjusted, runways, _, _, priorities, _ = prep("runway_closure")
    result = schedule_flights(adjusted, runways, priorities)
    assert result["solved"]
    assert all(a["runway_id"] == "R1" for a in result["assignments"])
    assert result["stats"]["candidate_assignments"] > 0
    assert "branches_pruned" in result["stats"]


def test_weather_route_changes_effective_eta():
    flights, _, _, _, blocked, _, impacts = prep("weather")
    assert "WP1" in blocked
    ai101 = impacts["AI101"]
    assert ai101["route_delay"] > 0
    assert "WP2" in ai101["current_path"]
    assert ai101["effective_eta"] > [f for f in flights if f.flight_id == "AI101"][0].eta


def test_combined_scenario_emergency_eta_feeds_scheduler():
    flights, adjusted, runways, _, _, priorities, impacts = prep("combined")
    assert priorities["AI222"]["priority"] == "emergency"
    assert impacts["AI222"]["route_delay"] > 0
    result = schedule_flights(adjusted, runways, priorities)
    assert result["solved"]
    ai222 = [a for a in result["assignments"] if a["flight_id"] == "AI222"][0]
    assert ai222["slot"] >= impacts["AI222"]["effective_eta"]


def test_astar_route_exists_in_weather_scenario():
    _, _, _, graph, blocked, _, _ = prep("weather")
    results = compare_searches(graph, "NORTH", "AIRPORT", blocked)
    astar = [r for r in results if r["algorithm_key"] == "astar"][0]
    assert astar["found"]
    assert "WP1" not in astar["path"]
    assert "WP2" in astar["path"]


def test_airspace_serialization_has_nodes_and_edges():
    _, _, _, graph, blocked, _, _ = prep("combined")
    data = graph.to_dict(blocked)
    assert any(n["id"] == "AIRPORT" for n in data["nodes"])
    wp1 = [n for n in data["nodes"] if n["id"] == "WP1"][0]
    assert wp1["blocked"] is True
    assert len(data["edges"]) > 0


def test_search_contrast_separates_unweighted_and_weighted_search():
    _, _, _, graph, blocked, _, _ = prep("search_contrast")
    results = {
        r["algorithm_key"]: r
        for r in compare_searches(graph, "NORTH", "AIRPORT", blocked)
    }

    assert results["bfs"]["found"]
    assert results["ucs"]["found"]
    assert results["astar"]["found"]
    assert "WP1" in results["bfs"]["path"]
    assert "WP2" in results["ucs"]["path"]
    assert "WP2" in results["astar"]["path"]
    assert results["ucs"]["cost"] < results["bfs"]["cost"]
    assert results["astar"]["cost"] == results["ucs"]["cost"]


def test_csp_heuristics_reduce_backtracking_in_combined_case():
    _, adjusted, runways, _, _, priorities, _ = prep("combined")
    results = {r["strategy"]: r for r in compare_csp_strategies(adjusted, runways, priorities)}
    assert all(r["solved"] for r in results.values())
    assert results["mrv"]["stats"]["backtracks"] < results["plain"]["stats"]["backtracks"]
    assert results["mrv_fc"]["stats"]["backtracks"] <= results["mrv"]["stats"]["backtracks"]


def test_v5_forward_chaining_exposes_rule_ids():
    flights, _, _, _, _, _, _ = prep("emergency")
    target = [f for f in flights if f.flight_id == "AI222"][0]
    info = infer_flight_priority(target)
    rule_ids = [r["rule_id"] for r in info["rules_fired"]]
    assert "R1" in rule_ids
    assert "R4" in rule_ids
    assert info["priority"] == "emergency"


def test_v5_decision_trace_covers_full_pipeline():
    from core.explain import build_decision_traces

    flights, adjusted, runways, _, blocked, priorities, impacts = prep("combined")
    result = schedule_flights(adjusted, runways, priorities)
    assert result["solved"]

    traces = build_decision_traces(
        flights, runways, blocked, priorities, impacts, result
    )
    assert "AI222" in traces
    trace = traces["AI222"]
    assert trace["priority"] == "emergency"
    assert [s["title"] for s in trace["stages"]] == [
        "Observed Facts",
        "Forward Chaining",
        "A* Route Assessment",
        "CSP Domain & Constraints",
        "Priority-Weighted Optimization",
        "Final Decision",
    ]
    flattened = " ".join(
        item for stage in trace["stages"] for item in stage["items"]
    )
    assert "R1" in flattened
    assert "R4" in flattened
    assert "R2" in flattened  # closed runway appears in CSP-domain explanation
    assert "total" in flattened.lower()



def test_v5_delay_metrics_separate_route_csp_and_total_delay():
    from core.explain import compute_delay_metrics

    flights, adjusted, runways, _, _, priorities, impacts = prep("combined")
    result = schedule_flights(adjusted, runways, priorities)
    assert result["solved"]

    for row in result["assignments"]:
        row["route_delay"] = impacts[row["flight_id"]]["route_delay"]

    metrics = compute_delay_metrics(result["assignments"])
    assert metrics["average_route_delay"] > 0
    assert metrics["average_total_delay"] >= result["stats"]["average_delay"]
    assert metrics["emergency_total_delay"] >= result["stats"]["emergency_delay"]


def test_v5_combined_global_optimum_is_77_and_ai222_is_1013():
    _, adjusted, runways, _, _, priorities, _ = prep("combined")
    result = schedule_flights(adjusted, runways, priorities)
    assert result["solved"]
    assert result["stats"]["fixed_horizon_used"] is False
    assert result["stats"]["best_weighted_cost"] == 77
    ai222 = [a for a in result["assignments"] if a["flight_id"] == "AI222"][0]
    assert ai222["slot"] == 13
    assert ai222["delay"] == 0


def test_v5_exact_validator_matches_optimizer_in_combined_case():
    from core.validator import validate_single_runway_optimum

    _, adjusted, runways, _, _, priorities, _ = prep("combined")
    result = schedule_flights(adjusted, runways, priorities)
    validation = validate_single_runway_optimum(adjusted, runways, priorities)
    assert validation["available"] is True
    assert validation["permutations_checked"] == 40320
    assert validation["best_weighted_cost"] == 77
    assert validation["best_weighted_cost"] == result["stats"]["best_weighted_cost"]
