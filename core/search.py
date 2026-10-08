import heapq
import math
from collections import deque
from time import perf_counter


DISPLAY_NAMES = {
    "bfs": "BFS",
    "ucs": "UCS",
    "greedy": "Greedy Best-First",
    "astar": "A*",
}


class AirspaceGraph:
    def __init__(self):
        self.edges = {}
        self.coords = {}
        self.risk = {}
        self.congestion = {}

    def add_node(self, node, x, y, risk=0, congestion=0):
        self.edges.setdefault(node, [])
        self.coords[node] = (x, y)
        self.risk[node] = risk
        self.congestion[node] = congestion

    def add_edge(self, a, b, distance):
        self.edges.setdefault(a, []).append((b, distance))
        self.edges.setdefault(b, []).append((a, distance))

    def heuristic(self, node, goal):
        x1, y1 = self.coords[node]
        x2, y2 = self.coords[goal]
        return math.hypot(x1 - x2, y1 - y2)

    def edge_cost(self, a, b, distance):
        # Destination-node penalties simulate congestion and weather/risk.
        return (
            distance
            + 2.5 * self.risk.get(b, 0)
            + 1.5 * self.congestion.get(b, 0)
        )

    def to_dict(self, blocked=None):
        blocked = set(blocked or [])
        nodes = []
        for node in sorted(self.coords):
            x, y = self.coords[node]
            nodes.append({
                "id": node,
                "x": x,
                "y": y,
                "risk": self.risk.get(node, 0),
                "congestion": self.congestion.get(node, 0),
                "blocked": node in blocked,
            })

        seen = set()
        edge_list = []
        for a, neighbours in self.edges.items():
            for b, distance in neighbours:
                key = tuple(sorted((a, b)))
                if key in seen:
                    continue
                seen.add(key)
                edge_list.append({"a": a, "b": b, "distance": distance})

        edge_list.sort(key=lambda e: (e["a"], e["b"]))
        return {"nodes": nodes, "edges": edge_list}


def reconstruct(parent, goal):
    if goal not in parent:
        return []
    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = parent[cur]
    return list(reversed(path))


def path_cost(graph, path):
    if not path:
        return None
    cost = 0.0
    for a, b in zip(path, path[1:]):
        for nxt, dist in graph.edges[a]:
            if nxt == b:
                cost += graph.edge_cost(a, b, dist)
                break
    return round(cost, 2)


def bfs(graph, start, goal, blocked):
    q = deque([start])
    parent = {start: None}
    explored = 0

    while q:
        node = q.popleft()
        explored += 1
        if node == goal:
            break
        for nxt, _ in graph.edges[node]:
            if nxt in blocked or nxt in parent:
                continue
            parent[nxt] = node
            q.append(nxt)

    return reconstruct(parent, goal), explored


def ucs(graph, start, goal, blocked):
    pq = [(0.0, start)]
    parent = {start: None}
    best = {start: 0.0}
    explored = 0

    while pq:
        cost, node = heapq.heappop(pq)
        if cost != best[node]:
            continue
        explored += 1
        if node == goal:
            break

        for nxt, dist in graph.edges[node]:
            if nxt in blocked:
                continue
            nc = cost + graph.edge_cost(node, nxt, dist)
            if nc < best.get(nxt, float("inf")):
                best[nxt] = nc
                parent[nxt] = node
                heapq.heappush(pq, (nc, nxt))

    return reconstruct(parent, goal), explored


def greedy(graph, start, goal, blocked):
    pq = [(graph.heuristic(start, goal), start)]
    parent = {start: None}
    seen = {start}
    explored = 0

    while pq:
        _, node = heapq.heappop(pq)
        explored += 1
        if node == goal:
            break

        for nxt, _ in graph.edges[node]:
            if nxt in blocked or nxt in seen:
                continue
            seen.add(nxt)
            parent[nxt] = node
            heapq.heappush(pq, (graph.heuristic(nxt, goal), nxt))

    return reconstruct(parent, goal), explored


def astar(graph, start, goal, blocked):
    pq = [(graph.heuristic(start, goal), 0.0, start)]
    parent = {start: None}
    best_g = {start: 0.0}
    explored = 0

    while pq:
        _, g, node = heapq.heappop(pq)
        if g != best_g[node]:
            continue
        explored += 1

        if node == goal:
            break

        for nxt, dist in graph.edges[node]:
            if nxt in blocked:
                continue
            ng = g + graph.edge_cost(node, nxt, dist)
            if ng < best_g.get(nxt, float("inf")):
                best_g[nxt] = ng
                parent[nxt] = node
                f = ng + graph.heuristic(nxt, goal)
                heapq.heappush(pq, (f, ng, nxt))

    return reconstruct(parent, goal), explored


def run_search(graph, algorithm, start, goal, blocked=None):
    blocked = set(blocked or [])
    blocked.discard(start)
    blocked.discard(goal)

    fn = {
        "bfs": bfs,
        "ucs": ucs,
        "greedy": greedy,
        "astar": astar,
    }[algorithm]

    t0 = perf_counter()
    path, explored = fn(graph, start, goal, blocked)
    elapsed = (perf_counter() - t0) * 1000

    return {
        "algorithm_key": algorithm,
        "algorithm": DISPLAY_NAMES[algorithm],
        "path": path,
        "cost": path_cost(graph, path),
        "nodes_explored": explored,
        "runtime_ms": round(elapsed, 4),
        "found": bool(path),
    }


def compare_searches(graph, start, goal, blocked=None):
    return [
        run_search(graph, a, start, goal, blocked)
        for a in ("bfs", "ucs", "greedy", "astar")
    ]
