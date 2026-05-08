from __future__ import annotations

from collections import defaultdict, OrderedDict
from dataclasses import dataclass
from functools import cache
import heapq
import math
import time
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

import matplotlib.pyplot as plt

@dataclass(frozen=True)
class Location:
    id: str
    name: str
    kind: str
    x: float
    y: float
    population: int = 0

@dataclass(frozen=True)
class Road:
    src: str
    dst: str
    distance_km: float
    capacity_vph: int
    condition: int
    existing: bool = True
    construction_cost_million: float = 0.0

@dataclass(frozen=True)
class TrafficPattern:
    road_id: str
    morning: int
    afternoon: int
    evening: int
    night: int

@dataclass(frozen=True)
class BusRoute:
    id: str
    stops: Tuple[str, ...]
    buses_assigned: int
    daily_passengers: int

@dataclass(frozen=True)
class TransitDemand:
    src: str
    dst: str
    daily_passengers: int

@dataclass(frozen=True)
class MetroLine:
    id: str
    name: str
    stations: Tuple[str, ...]
    daily_passengers: int

@dataclass
class PathResult:
    path: List[str]
    cost: float

@dataclass
class BusAllocationResult:
    allocations: Dict[str, int]
    estimated_served_passengers: int

@dataclass
class MaintenancePlan:
    selected_roads: List[Tuple[str, str]]
    total_benefit: int
    total_cost: int

@dataclass
class SignalPlan:
    green_times: Dict[str, int]
    cycle_length: int

@dataclass
class EmergencyPreemptionPlan:
    ordered_intersections: List[str]
    estimated_saved_minutes: float

@dataclass
class MSTResult:
    selected_edges: List[Road]
    score: float
    construction_cost_million: float

NEIGHBORHOODS: Dict[str, Location] = {
    "1": Location("1", "Maadi", "Residential", 31.25, 29.96, 250000),
    "2": Location("2", "Nasr City", "Mixed", 31.34, 30.06, 500000),
    "3": Location("3", "Downtown Cairo", "Business", 31.24, 30.04, 100000),
    "4": Location("4", "New Cairo", "Residential", 31.47, 30.03, 300000),
    "5": Location("5", "Heliopolis", "Mixed", 31.32, 30.09, 200000),
    "6": Location("6", "Zamalek", "Residential", 31.22, 30.06, 50000),
    "7": Location("7", "6th October City", "Mixed", 30.98, 29.93, 400000),
    "8": Location("8", "Giza", "Mixed", 31.21, 29.99, 550000),
    "9": Location("9", "Mohandessin", "Business", 31.20, 30.05, 180000),
    "10": Location("10", "Dokki", "Mixed", 31.21, 30.03, 220000),
    "11": Location("11", "Shubra", "Residential", 31.24, 30.11, 450000),
    "12": Location("12", "Helwan", "Industrial", 31.33, 29.85, 350000),
    "13": Location("13", "New Administrative Capital", "Government", 31.80, 30.02, 50000),
    "14": Location("14", "Al Rehab", "Residential", 31.49, 30.06, 120000),
    "15": Location("15", "Sheikh Zayed", "Residential", 30.94, 30.01, 150000),
}

FACILITIES: Dict[str, Location] = {
    "F1": Location("F1", "Cairo International Airport", "Airport", 31.41, 30.11),
    "F2": Location("F2", "Ramses Railway Station", "Transit Hub", 31.25, 30.06),
    "F3": Location("F3", "Cairo University", "Education", 31.21, 30.03),
    "F4": Location("F4", "Al-Azhar University", "Education", 31.26, 30.05),
    "F5": Location("F5", "Egyptian Museum", "Tourism", 31.23, 30.05),
    "F6": Location("F6", "Cairo International Stadium", "Sports", 31.30, 30.07),
    "F7": Location("F7", "Smart Village", "Business", 30.97, 30.07),
    "F8": Location("F8", "Cairo Festival City", "Commercial", 31.40, 30.03),
    "F9": Location("F9", "Qasr El Aini Hospital", "Medical", 31.23, 30.03),
    "F10": Location("F10", "Maadi Military Hospital", "Medical", 31.25, 29.95),
}

LOCATIONS: Dict[str, Location] = {**NEIGHBORHOODS, **FACILITIES}

EXISTING_ROADS: List[Road] = [
    Road("1", "3", 8.5, 3000, 7), Road("1", "8", 6.2, 2500, 6), Road("2", "3", 5.9, 2800, 8),
    Road("2", "5", 4.0, 3200, 9), Road("3", "5", 6.1, 3500, 7), Road("3", "6", 3.2, 2000, 8),
    Road("3", "9", 4.5, 2600, 6), Road("3", "10", 3.8, 2400, 7), Road("4", "2", 15.2, 3800, 9),
    Road("4", "14", 5.3, 3000, 10), Road("5", "11", 7.9, 3100, 7), Road("6", "9", 2.2, 1800, 8),
    Road("7", "8", 24.5, 3500, 8), Road("7", "15", 9.8, 3000, 9), Road("8", "10", 3.3, 2200, 7),
    Road("8", "12", 14.8, 2600, 5), Road("9", "10", 2.1, 1900, 7), Road("10", "11", 8.7, 2400, 6),
    Road("11", "F2", 3.6, 2200, 7), Road("12", "1", 12.7, 2800, 6), Road("13", "4", 45.0, 4000, 10),
    Road("14", "13", 35.5, 3800, 9), Road("15", "7", 9.8, 3000, 9), Road("F1", "5", 7.5, 3500, 9),
    Road("F1", "2", 9.2, 3200, 8), Road("F2", "3", 2.5, 2000, 7), Road("F7", "15", 8.3, 2800, 8),
    Road("F9", "F3", 1.4, 1700, 8),
    Road("F8", "4", 6.1, 3000, 9),
]

POTENTIAL_NEW_ROADS: List[Road] = [
    Road("1", "4", 22.8, 4000, 10, existing=False, construction_cost_million=450),
    Road("1", "14", 25.3, 3800, 10, existing=False, construction_cost_million=500),
    Road("2", "13", 48.2, 4500, 10, existing=False, construction_cost_million=950),
    Road("3", "13", 56.7, 4500, 10, existing=False, construction_cost_million=1100),
    Road("5", "4", 16.8, 3500, 10, existing=False, construction_cost_million=320),
    Road("6", "8", 7.5, 2500, 10, existing=False, construction_cost_million=150),
    Road("7", "13", 82.3, 4000, 10, existing=False, construction_cost_million=1600),
    Road("9", "11", 6.9, 2800, 10, existing=False, construction_cost_million=140),
    Road("10", "F7", 27.4, 3200, 10, existing=False, construction_cost_million=550),
    Road("11", "13", 62.1, 4200, 10, existing=False, construction_cost_million=1250),
    Road("12", "14", 30.5, 3600, 10, existing=False, construction_cost_million=610),
    Road("14", "5", 18.2, 3300, 10, existing=False, construction_cost_million=360),
    Road("15", "9", 22.7, 3000, 10, existing=False, construction_cost_million=450),
    Road("F1", "13", 40.2, 4000, 10, existing=False, construction_cost_million=800),
    Road("F7", "9", 26.8, 3200, 10, existing=False, construction_cost_million=540),
]

DERIVED_ACCESS_ROADS: List[Road] = [
    Road("F3", "10", 0.6, 1800, 8), Road("F4", "3", 1.6, 1700, 8),
    Road("F5", "3", 1.2, 1700, 8), Road("F6", "5", 2.4, 1800, 8),
    Road("F9", "10", 2.3, 1600, 8), Road("F10", "1", 1.2, 1600, 8),
]

TRAFFIC_PATTERNS: Dict[str, TrafficPattern] = {
    "1-3": TrafficPattern("1-3", 2800, 1500, 2600, 800), "1-8": TrafficPattern("1-8", 2200, 1200, 2100, 600),
    "2-3": TrafficPattern("2-3", 2700, 1400, 2500, 700), "2-5": TrafficPattern("2-5", 3000, 1600, 2800, 650),
    "3-5": TrafficPattern("3-5", 3200, 1700, 3100, 800), "3-6": TrafficPattern("3-6", 1800, 1400, 1900, 500),
    "3-9": TrafficPattern("3-9", 2400, 1300, 2200, 550), "3-10": TrafficPattern("3-10", 2300, 1200, 2100, 500),
    "4-2": TrafficPattern("4-2", 3600, 1800, 3300, 750), "4-14": TrafficPattern("4-14", 2800, 1600, 2600, 600),
    "5-11": TrafficPattern("5-11", 2900, 1500, 2700, 650), "6-9": TrafficPattern("6-9", 1700, 1300, 1800, 450),
    "7-8": TrafficPattern("7-8", 3200, 1700, 3000, 700), "7-15": TrafficPattern("7-15", 2800, 1500, 2600, 600),
    "8-10": TrafficPattern("8-10", 2000, 1100, 1900, 450), "8-12": TrafficPattern("8-12", 2400, 1300, 2200, 500),
    "9-10": TrafficPattern("9-10", 1800, 1200, 1700, 400), "10-11": TrafficPattern("10-11", 2200, 1300, 2100, 500),
    "11-F2": TrafficPattern("11-F2", 2100, 1200, 2000, 450), "12-1": TrafficPattern("12-1", 2600, 1400, 2400, 550),
    "13-4": TrafficPattern("13-4", 3800, 2000, 3500, 800), "14-13": TrafficPattern("14-13", 3600, 1900, 3300, 750),
    "15-7": TrafficPattern("15-7", 2800, 1500, 2600, 600), "F1-5": TrafficPattern("F1-5", 3300, 2200, 3100, 1200),
    "F1-2": TrafficPattern("F1-2", 3000, 2000, 2800, 1100), "F2-3": TrafficPattern("F2-3", 1900, 1600, 1800, 900),
    "F9-F3": TrafficPattern("F9-F3", 1450, 900, 1300, 500),
    "F7-15": TrafficPattern("F7-15", 2600, 1500, 2400, 550), "F8-4": TrafficPattern("F8-4", 2800, 1600, 2600, 600),
}

BUS_ROUTES: List[BusRoute] = [
    BusRoute("B1", ("1", "3", "6", "9"), 25, 35000), BusRoute("B2", ("7", "15", "8", "10", "3"), 30, 42000),
    BusRoute("B3", ("2", "5", "F1"), 20, 28000), BusRoute("B4", ("4", "14", "2", "3"), 22, 31000),
    BusRoute("B5", ("8", "12", "1"), 18, 25000), BusRoute("B6", ("11", "5", "2"), 24, 33000),
    BusRoute("B7", ("13", "4", "14"), 15, 21000), BusRoute("B8", ("F7", "15", "7"), 12, 17000),
    BusRoute("B9", ("1", "8", "10", "9", "6"), 28, 39000), BusRoute("B10", ("F8", "4", "2", "5"), 20, 28000),
]

METRO_LINES: Tuple[MetroLine, ...] = (
    MetroLine("M1", "Line 1 (Helwan–New Marg)", ("12", "1", "3", "F2", "11"), 1_500_000),
    MetroLine("M2", "Line 2 (Shubra–Giza)", ("11", "F2", "3", "10", "8"), 1_200_000),
    MetroLine("M3", "Line 3 (Airport–Imbaba)", ("F1", "5", "2", "3", "9"), 800_000),
)

TRANSIT_DEMAND: List[TransitDemand] = [
    TransitDemand("3", "5", 15000), TransitDemand("1", "3", 12000), TransitDemand("2", "3", 18000),
    TransitDemand("F2", "11", 25000), TransitDemand("F1", "3", 20000), TransitDemand("7", "3", 14000),
    TransitDemand("4", "3", 16000), TransitDemand("8", "3", 22000), TransitDemand("3", "9", 13000),
    TransitDemand("5", "2", 17000), TransitDemand("11", "3", 24000), TransitDemand("12", "3", 11000),
    TransitDemand("1", "8", 9000), TransitDemand("7", "F7", 18000), TransitDemand("4", "F8", 12000),
    TransitDemand("13", "3", 8000), TransitDemand("14", "4", 7000),
]

NODE_STYLE = {
    "Residential": ("o", "#5B8FF9"), "Mixed": ("s", "#61DDAA"), "Business": ("D", "#65789B"),
    "Industrial": ("^", "#F6BD16"), "Government": ("P", "#7262FD"), "Airport": ("*", "#FF9845"),
    "Transit Hub": ("X", "#78D3F8"), "Education": ("h", "#9661BC"), "Tourism": ("v", "#F08BB4"),
    "Sports": ("<", "#6DC8EC"), "Commercial": (">", "#269A99"), "Medical": ("8", "#E86452"),
}

CRITICAL_TYPES = {"Medical", "Transit Hub", "Government", "Airport"}

class TransportGraph:
    def __init__(self, roads: Iterable[Road]) -> None:
        self.nodes = dict(LOCATIONS)
        self.adj: Dict[str, List[Road]] = defaultdict(list)
        self.edges: List[Road] = []
        for road in roads:
            self.adj[road.src].append(road)
            self.adj[road.dst].append(
                Road(road.dst, road.src, road.distance_km, road.capacity_vph,
                     road.condition, road.existing, road.construction_cost_million)
            )
            self.edges.append(road)

    def neighbors(self, node_id: str) -> List[Road]:
        return self.adj.get(node_id, [])

    def euclidean_distance(self, src: str, dst: str) -> float:
        a = self.nodes[src]
        b = self.nodes[dst]
        return math.hypot(a.x - b.x, a.y - b.y) * 111.0

    def traffic_pattern(self, src: str, dst: str) -> Optional[TrafficPattern]:
        return TRAFFIC_PATTERNS.get(f"{src}-{dst}") or TRAFFIC_PATTERNS.get(f"{dst}-{src}")

    def edge_travel_time_minutes(self, src: str, dst: str, slot: str = "afternoon") -> float:
        edge = next((edge for edge in self.adj[src] if edge.dst == dst), None)
        if edge is None:
            raise KeyError(f"No edge between {src} and {dst}")
        base_speed_kmh = 35.0 + (edge.condition - 5) * 1.5
        pattern = self.traffic_pattern(src, dst)
        if pattern is not None:
            flow = getattr(pattern, slot)
            congestion_ratio = flow / max(edge.capacity_vph, 1)
            penalty = 1.0 + max(0.0, congestion_ratio - 0.6) * 1.8
        else:
            penalty = 1.0
        effective_speed = max(8.0, base_speed_kmh / penalty)
        return (edge.distance_km / effective_speed) * 60.0

    def path_distance(self, path: Sequence[str]) -> float:
        total = 0.0
        for i in range(len(path) - 1):
            edge = next(edge for edge in self.adj[path[i]] if edge.dst == path[i + 1])
            total += edge.distance_km
        return total

    def path_time(self, path: Sequence[str], slot: str = "afternoon") -> float:
        total = 0.0
        for i in range(len(path) - 1):
            total += self.edge_travel_time_minutes(path[i], path[i + 1], slot)
        return total

DEFAULT_ROUTING_GRAPH = TransportGraph([*EXISTING_ROADS, *DERIVED_ACCESS_ROADS])

def _reconstruct(parent: Dict[str, str], target: str) -> List[str]:
    path = [target]
    while target in parent:
        target = parent[target]
        path.append(target)
    return list(reversed(path))

def _dijkstra_impl(graph: TransportGraph, source: str, target: str, slot: str, closed_edges: Set[Tuple[str, str]]) -> PathResult:
    pq: List[Tuple[float, str]] = [(0.0, source)]
    dist: Dict[str, float] = {source: 0.0}
    parent: Dict[str, str] = {}

    while pq:
        cur_cost, node = heapq.heappop(pq)
        if node == target:
            return PathResult(_reconstruct(parent, target), round(cur_cost, 2))
        if cur_cost > dist.get(node, float("inf")):
            continue
        for edge in graph.neighbors(node):
            if (node, edge.dst) in closed_edges or (edge.dst, node) in closed_edges:
                continue
            next_cost = cur_cost + graph.edge_travel_time_minutes(node, edge.dst, slot)
            if next_cost < dist.get(edge.dst, float("inf")):
                dist[edge.dst] = next_cost
                parent[edge.dst] = node
                heapq.heappush(pq, (next_cost, edge.dst))
    return PathResult([], float("inf"))

_ROUTE_MEMO_MAX = 1024
_route_memo: "OrderedDict[Tuple[str, str, str], Tuple[Tuple[str, ...], float]]" = OrderedDict()


def _route_memo_get(key: Tuple[str, str, str]) -> Optional[PathResult]:
    if key not in _route_memo:
        return None
    path_t, cost = _route_memo[key]
    _route_memo.move_to_end(key)
    return PathResult(list(path_t), cost)


def _route_memo_set(key: Tuple[str, str, str], result: PathResult) -> None:
    if math.isinf(result.cost) or len(result.path) == 0:
        return
    path_t = tuple(result.path)
    _route_memo[key] = (path_t, result.cost)
    _route_memo.move_to_end(key)
    while len(_route_memo) > _ROUTE_MEMO_MAX:
        _route_memo.popitem(last=False)


def dijkstra_shortest_path(graph: TransportGraph, source: str, target: str, slot: str = "afternoon", closed_edges: Optional[Set[Tuple[str, str]]] = None) -> PathResult:
    # Time complexity: O((V + E) log V) with a binary heap.
    # Space complexity: O(V) for dist/parent maps + priority queue.
    closed_edges = closed_edges or set()
    memo_key = (source, target, slot)
    if not closed_edges and graph is DEFAULT_ROUTING_GRAPH:
        cached = _route_memo_get(memo_key)
        if cached is not None:
            return cached
    result = _dijkstra_impl(graph, source, target, slot, closed_edges)
    if not closed_edges and graph is DEFAULT_ROUTING_GRAPH:
        _route_memo_set(memo_key, result)
    return result

def a_star_emergency_route(graph: TransportGraph, source: str, target: str, slot: str = "afternoon") -> PathResult:
    avg_emergency_speed = 55.0
    open_heap: List[Tuple[float, str]] = [(0.0, source)]
    g_score: Dict[str, float] = {source: 0.0}
    parent: Dict[str, str] = {}

    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current == target:
            return PathResult(_reconstruct(parent, target), round(g_score[target], 2))
        for edge in graph.neighbors(current):
            base_time = graph.edge_travel_time_minutes(current, edge.dst, slot)
            if slot in {"morning", "evening"}:
                base_time *= 0.82
            tentative = g_score[current] + base_time
            if tentative < g_score.get(edge.dst, float("inf")):
                parent[edge.dst] = current
                g_score[edge.dst] = tentative
                heuristic = (graph.euclidean_distance(edge.dst, target) / avg_emergency_speed) * 60.0
                heapq.heappush(open_heap, (tentative + heuristic, edge.dst))
    return PathResult([], float("inf"))

def a_star_shortest_path(graph: TransportGraph, source: str, target: str, slot: str = "afternoon") -> PathResult:
    """General A* for regular routing (no emergency-only travel-time boost)."""
    avg_speed = 50.0
    open_heap: List[Tuple[float, str]] = [(0.0, source)]
    g_score: Dict[str, float] = {source: 0.0}
    parent: Dict[str, str] = {}

    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current == target:
            return PathResult(_reconstruct(parent, target), round(g_score[target], 2))
        for edge in graph.neighbors(current):
            tentative = g_score[current] + graph.edge_travel_time_minutes(current, edge.dst, slot)
            if tentative < g_score.get(edge.dst, float("inf")):
                parent[edge.dst] = current
                g_score[edge.dst] = tentative
                heuristic = (graph.euclidean_distance(edge.dst, target) / avg_speed) * 60.0
                heapq.heappush(open_heap, (tentative + heuristic, edge.dst))
    return PathResult([], float("inf"))

def time_dependent_shortest_path(graph: TransportGraph, source: str, target: str, departure_slot: str) -> PathResult:
    return dijkstra_shortest_path(graph, source, target, slot=departure_slot)

class DisjointSet:
    def __init__(self, items: Iterable[str]) -> None:
        self.parent = {item: item for item in items}
        self.rank = {item: 0 for item in items}

    def find(self, item: str) -> str:
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, a: str, b: str) -> bool:
        ra = self.find(a)
        rb = self.find(b)
        if ra == rb:
            return False
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1
        return True

def _population_score(node_id: str) -> float:
    return LOCATIONS[node_id].population / 1_000_000 if node_id in LOCATIONS else 0.0

def _is_critical(node_id: str) -> bool:
    return LOCATIONS[node_id].kind in CRITICAL_TYPES

@cache
def modified_edge_score(road: Road) -> float:
    pop_bonus = min(0.35, _population_score(road.src) + _population_score(road.dst))
    critical_bonus = 0.18 if _is_critical(road.src) or _is_critical(road.dst) else 0.0
    condition_bonus = (road.condition - 5) * 0.03 if road.existing else 0.0
    if road.existing:
        base = road.distance_km * (1.15 - condition_bonus)
    else:
        base = road.distance_km + road.construction_cost_million / 55.0
    capacity_discount = min(0.12, road.capacity_vph / 50000.0)
    weighted = base * (1.0 - pop_bonus - critical_bonus - capacity_discount)
    return max(weighted, road.distance_km * 0.35)

def build_modified_mst(existing_roads: List[Road], candidate_roads: List[Road], budget_million: float = 1000.0, include_potential_roads: bool = True) -> MSTResult:
    # Baseline Kruskal phase complexity: O(E log E) time from sorting, O(V) DSU space.
    # Budget-improvement phase scans selected edges for each candidate:
    # O(C * V) time in practice (C candidates, V-1 selected edges).
    all_nodes: Set[str] = set()
    for road in [*existing_roads, *candidate_roads]:
        all_nodes.add(road.src)
        all_nodes.add(road.dst)

    # Step 1: Build baseline MST using only existing roads
    dsu = DisjointSet(all_nodes)
    selected: List[Road] = []
    total_score = 0.0
    total_cost = 0.0

    for road in sorted(existing_roads, key=modified_edge_score):
        if dsu.union(road.src, road.dst):
            selected.append(road)
            total_score += modified_edge_score(road)
        if len(selected) == len(all_nodes) - 1:
            break

    if not include_potential_roads:
        return MSTResult(selected, round(total_score, 2), round(total_cost, 2))

    # Step 2: Try to swap in affordable new roads that improve the MST score.
    # A new road can replace the worst existing road in the MST if it scores better.
    remaining_budget = budget_million

    affordable = sorted(
        [r for r in candidate_roads if r.construction_cost_million <= remaining_budget],
        key=modified_edge_score
    )

    for new_road in affordable:
        if new_road.construction_cost_million > remaining_budget:
            continue
        new_score = modified_edge_score(new_road)
        worst_road = None
        worst_score = -1.0
        for existing in selected:
            if not existing.existing:
                continue
            escore = modified_edge_score(existing)
            if escore > new_score * 1.05 and escore > worst_score:
                worst_road = existing
                worst_score = escore

        if worst_road is not None:
            selected.remove(worst_road)
            selected.append(new_road)
            total_score = total_score - worst_score + new_score
            total_cost += new_road.construction_cost_million
            remaining_budget -= new_road.construction_cost_million

    return MSTResult(selected, round(total_score, 2), round(total_cost, 2))

def optimize_bus_allocation(extra_buses: int, specific_route: str = "ALL", bus_capacity_per_day: int = 1400) -> BusAllocationResult:
    if specific_route != "ALL":
        routes = [(route.id, route.buses_assigned, route.daily_passengers) 
                  for route in BUS_ROUTES if route.id == specific_route]
    else:
        routes = [(route.id, route.buses_assigned, route.daily_passengers) for route in BUS_ROUTES]

    memo: Dict[Tuple[int, int], Tuple[int, Tuple[int, ...]]] = {}

    def dp(index: int, remaining: int) -> Tuple[int, Tuple[int, ...]]:
        if index == len(routes):
            return 0, ()
        if (index, remaining) in memo:
            return memo[(index, remaining)]
        route_id, base_buses, demand = routes[index]
        best_score = -1
        best_pattern: Tuple[int, ...] = ()
        for add in range(remaining + 1):
            effective_capacity = (base_buses + add) * bus_capacity_per_day
            served_here = min(demand, effective_capacity)
            tail_score, tail_pattern = dp(index + 1, remaining - add)
            total = served_here + tail_score
            if total > best_score:
                best_score = total
                best_pattern = (add,) + tail_pattern
        memo[(index, remaining)] = (best_score, best_pattern)
        return best_score, best_pattern

    score, pattern = dp(0, extra_buses)
    allocations = {routes[i][0]: routes[i][1] + pattern[i] for i in range(len(routes))}
    return BusAllocationResult(allocations, score)

def optimize_road_maintenance(budget_million: int) -> MaintenancePlan:
    # 0/1 knapsack DP over candidate roads.
    # Time complexity: O(N * B), Space complexity: O(N * B),
    # where N = candidate repairs and B = budget_million integer capacity.
    candidate_repairs = []
    for road in EXISTING_ROADS:
        if road.condition <= 7:
            repair_cost = int(max(40, road.distance_km * (12 - road.condition) * 2))
            benefit = int(road.capacity_vph / 100 + (10 - road.condition) * 18)
            candidate_repairs.append((road.src, road.dst, repair_cost, benefit))

    n = len(candidate_repairs)
    dp = [[0] * (budget_million + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        _, _, cost, benefit = candidate_repairs[i - 1]
        for b in range(budget_million + 1):
            dp[i][b] = dp[i - 1][b]
            if cost <= b:
                dp[i][b] = max(dp[i][b], dp[i - 1][b - cost] + benefit)

    selected: List[Tuple[str, str]] = []
    b = budget_million
    for i in range(n, 0, -1):
        if dp[i][b] != dp[i - 1][b]:
            src, dst, cost, _ = candidate_repairs[i - 1]
            selected.append((src, dst))
            b -= cost
    total_cost = budget_million - b
    return MaintenancePlan(selected[::-1], dp[n][budget_million], total_cost)

def optimize_signal_cycle(intersection_queues: Dict[str, int], cycle_length: int = 120, min_green: int = 12) -> SignalPlan:
    # Greedy proportional allocation:
    # Works well for high-throughput balancing, but may be suboptimal when
    # spillback/phase-coupling constraints dominate (non-convex intersection dynamics).
    total_queue = max(sum(intersection_queues.values()), 1)
    provisional: Dict[str, int] = {}
    for lane_group, queue in intersection_queues.items():
        proportional = int(cycle_length * (queue / total_queue))
        provisional[lane_group] = max(min_green, proportional)
    current_total = sum(provisional.values())
    while current_total > cycle_length:
        key = max(provisional, key=provisional.get)
        if provisional[key] > min_green:
            provisional[key] -= 1
            current_total -= 1
        else:
            break
    while current_total < cycle_length:
        key = max(intersection_queues, key=intersection_queues.get)
        provisional[key] += 1
        current_total += 1
    return SignalPlan(provisional, cycle_length)

def emergency_vehicle_preemption(route_intersections: List[Tuple[str, int]]) -> EmergencyPreemptionPlan:
    # Greedy priority ordering by current congestion severity.
    # Usually effective for urgent clearance, but globally suboptimal when
    # downstream blocking causes delayed secondary bottlenecks.
    ordered = sorted(route_intersections, key=lambda item: item[1], reverse=True)
    saved_minutes = sum(congestion / 120.0 for _, congestion in ordered)
    return EmergencyPreemptionPlan([name for name, _ in ordered], round(saved_minutes, 2))

def prioritize_roads_for_signal(slot: str = "morning") -> List[dict]:
    """Return roads ranked by flow/capacity pressure for signal prioritization demos."""
    ranked = []
    for rd in EXISTING_ROADS:
        pat = TRAFFIC_PATTERNS.get(f"{rd.src}-{rd.dst}") or TRAFFIC_PATTERNS.get(f"{rd.dst}-{rd.src}")
        if not pat:
            continue
        flow = getattr(pat, slot, pat.afternoon)
        ratio = flow / max(1, rd.capacity_vph)
        ranked.append(
            {
                "road": f"{rd.src}-{rd.dst}",
                "flow": flow,
                "capacity": rd.capacity_vph,
                "ratio": round(ratio, 4),
            }
        )
    # Prioritize roads with highest absolute flow first, then pressure ratio.
    # This matches corridor-style control where heavily used arterials are favored.
    ranked.sort(key=lambda r: (-r["flow"], -r["ratio"], r["road"]))
    return ranked

class TransportSystem:
    def __init__(self) -> None:
        self.existing_roads = [*EXISTING_ROADS, *DERIVED_ACCESS_ROADS]
        self.graph = DEFAULT_ROUTING_GRAPH
        self.combined_graph = TransportGraph([*self.existing_roads, *POTENTIAL_NEW_ROADS])
        self.location_options = {node_id: f"{node_id} - {loc.name}" for node_id, loc in LOCATIONS.items()}
        self.road_options = [f"{road.src}-{road.dst}" for road in self.existing_roads]
        self.hospital_options = ["F9", "F10"]

    def build_mst(self, budget: float = 1000.0, include_new: bool = True) -> MSTResult:
        return build_modified_mst(self.existing_roads, POTENTIAL_NEW_ROADS, budget, include_new)

    def standard_route(self, source: str, target: str, slot: str, closed_pairs: Optional[Set[Tuple[str, str]]] = None) -> PathResult:
        return dijkstra_shortest_path(self.graph, source, target, slot=slot, closed_edges=closed_pairs)

    def emergency_route(self, source: str, target: str, slot: str) -> PathResult:
        return a_star_emergency_route(self.graph, source, target, slot=slot)

    def a_star_route(self, source: str, target: str, slot: str) -> PathResult:
        return a_star_shortest_path(self.graph, source, target, slot=slot)

    def adaptive_route(self, source: str, target: str, slot: str) -> PathResult:
        return time_dependent_shortest_path(self.graph, source, target, departure_slot=slot)

    def bus_optimization(self, extra_buses: int, specific_route: str = "ALL") -> BusAllocationResult:
        return optimize_bus_allocation(extra_buses, specific_route)

    def maintenance_optimization(self, budget_million: int) -> MaintenancePlan:
        return optimize_road_maintenance(budget_million)

    def traffic_signal_plan(self, ns: int, ew: int, left: int, ped: int, cycle: int = 120) -> SignalPlan:
        return optimize_signal_cycle({"North-South": ns, "East-West": ew, "Left-Turn": left, "Pedestrian": ped}, cycle_length=cycle)

    def preemption_plan(self, tahrir: int, ramses: int, qasr: int, dokki: int) -> EmergencyPreemptionPlan:
        return emergency_vehicle_preemption([("Tahrir", tahrir), ("Ramses", ramses), ("Qasr El Aini", qasr), ("Dokki", dokki)])

    def signal_priority_roads(self, slot: str = "morning") -> List[dict]:
        return prioritize_roads_for_signal(slot)

    def run_algorithm_race(self, source: str, target: str) -> dict:
        start_d = time.perf_counter()
        res_d = self.standard_route(source, target, "morning")
        time_d = (time.perf_counter() - start_d) * 1000

        start_a = time.perf_counter()
        res_a = self.a_star_route(source, target, "morning")
        time_a = (time.perf_counter() - start_a) * 1000

        return {
            "dijkstra_nodes": len(res_d.path),
            "astar_nodes": len(res_a.path),
            "dijkstra_time": round(time_d, 4),
            "astar_time": round(time_a, 4)
        }

    def plot_network(self, mode: str = "existing", route: Optional[Sequence[str]] = None):
        if mode == "existing":
            roads = self.existing_roads
            title = "Existing + Access Roads"
        elif mode == "combined":
            roads = [*self.existing_roads, *POTENTIAL_NEW_ROADS]
            title = "Existing + Candidate Roads"
        elif mode == "mst":
            roads = self.build_mst().selected_edges
            title = "Modified MST Infrastructure Design"
        else:
            roads = self.existing_roads
            title = "Route View"

        fig, ax = plt.subplots(figsize=(10.5, 7.2))
        for road in roads:
            a = LOCATIONS[road.src]
            b = LOCATIONS[road.dst]
            linestyle = "-" if road.existing else "--"
            alpha = 0.8 if road.existing else 0.5
            ax.plot([a.x, b.x], [a.y, b.y], linestyle=linestyle, linewidth=1.4, alpha=alpha, color="#7a7a7a")

        if route and len(route) > 1:
            for i in range(len(route) - 1):
                a = LOCATIONS[route[i]]
                b = LOCATIONS[route[i + 1]]
                ax.plot([a.x, b.x], [a.y, b.y], linewidth=3.2, color="#D7263D")
            title = f"{title} with Highlighted Route"

        for node in LOCATIONS.values():
            marker, color = NODE_STYLE.get(node.kind, ("o", "black"))
            size = 60 if node.population == 0 else max(60, node.population / 6000)
            ax.scatter(node.x, node.y, s=size, marker=marker, c=color)
            ax.text(node.x + 0.008, node.y + 0.004, f"{node.id}:{node.name}", fontsize=8)

        ax.set_title(title)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.grid(alpha=0.2)
        fig.tight_layout()
        return fig