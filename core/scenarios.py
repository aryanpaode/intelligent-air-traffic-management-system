from .models import Flight, Runway
from .search import AirspaceGraph


def base_graph():
    g = AirspaceGraph()

    nodes = {
        "NORTH": (0, 8),
        "WEST": (-7, 2),
        "EAST": (7, 2),
        "WP1": (-2, 5),
        "WP2": (2, 5),
        "WP3": (-3, 1),
        "WP4": (3, 1),
        "HOLD_A": (-1, 3),
        "HOLD_B": (1, 3),
        "AIRPORT": (0, -2),
    }

    for n, (x, y) in nodes.items():
        g.add_node(n, x, y)

    edges = [
        ("NORTH", "WP1", 4),
        ("NORTH", "WP2", 4),
        ("WEST", "WP3", 5),
        ("EAST", "WP4", 5),
        ("WP1", "HOLD_A", 3),
        ("WP2", "HOLD_B", 3),
        ("WP1", "WP2", 3),
        ("WP3", "HOLD_A", 2),
        ("WP4", "HOLD_B", 2),
        ("HOLD_A", "HOLD_B", 2),
        ("HOLD_A", "AIRPORT", 4),
        ("HOLD_B", "AIRPORT", 4),
        ("WP3", "AIRPORT", 6),
        ("WP4", "AIRPORT", 6),
    ]

    for a, b, d in edges:
        g.add_edge(a, b, d)

    # Mild background congestion in holding areas.
    g.congestion["HOLD_A"] = 1
    g.congestion["HOLD_B"] = 1
    return g


def normal_scenario():
    flights = [
        Flight("AI101", "arrival", 0, "medium", "normal", False, "R1", "NORTH"),
        Flight("6E204", "arrival", 3, "medium", "low", False, "", "WEST"),
        Flight("UK315", "arrival", 5, "heavy", "normal", False, "R1", "EAST"),
        Flight("SG410", "departure", 7, "light", "normal", False, "R2", "AIRPORT"),
        Flight("AI222", "arrival", 9, "medium", "normal", False, "", "NORTH"),
        Flight("6E880", "departure", 11, "medium", "normal", False, "", "AIRPORT"),
        Flight("EK502", "arrival", 12, "heavy", "normal", False, "R2", "EAST"),
        Flight("QP113", "arrival", 14, "light", "normal", False, "", "WEST"),
    ]

    runways = [
        Runway("R1", True, ["light", "medium", "heavy"]),
        Runway("R2", True, ["light", "medium", "heavy"]),
    ]

    return flights, runways, base_graph(), set()


def load_scenario(name):
    flights, runways, graph, blocked = normal_scenario()

    if name == "runway_closure":
        runways[1].is_open = False

    elif name == "emergency":
        flights[4].fuel_status = "critical"

    elif name == "weather":
        # V3 deliberately blocks the normally preferred western approach.
        # The remaining eastern approach also carries weather risk, producing
        # a measurable A*-derived ETA shift for NORTH arrivals.
        blocked.add("WP1")
        graph.risk["HOLD_B"] = 3

    elif name == "combined":
        runways[1].is_open = False
        flights[4].fuel_status = "critical"
        blocked.add("WP1")
        graph.risk["HOLD_B"] = 4
        graph.congestion["HOLD_A"] = 3

    elif name == "search_contrast":
        # Deliberately educational scenario:
        # BFS/Greedy tend to take the first/closest western approach,
        # while UCS/A* see its high risk cost and prefer the eastern route.
        graph.risk["WP1"] = 3
        graph.risk["HOLD_A"] = 4

    return flights, runways, graph, blocked
