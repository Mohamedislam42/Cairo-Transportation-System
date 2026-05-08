from __future__ import annotations

import os
from typing import Optional, Set, Tuple

from flask import Flask, request, jsonify, render_template, Response

import base64
import io

_PROJECT_DIR = os.path.abspath(os.path.dirname(__file__))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from transport_core import (
    BUS_ROUTES,
    EXISTING_ROADS,
    LOCATIONS,
    METRO_LINES,
    TRAFFIC_PATTERNS,
    TransportSystem,
)

from traffic_predictor import TrafficPredictor

app = Flask(
    __name__,
    template_folder=os.path.join(_PROJECT_DIR, "templates"),
    static_folder=os.path.join(_PROJECT_DIR, "static"),
)
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

@app.after_request
def _avoid_stale_assets(resp):
    """Prevent the browser from keeping an old index.html/CSS/JS (common cause of 'nothing changed')."""
    if request.endpoint == "static" or request.path in ("/",):
        resp.headers.setdefault("Cache-Control", "no-store, max-age=0")
        resp.headers.setdefault("Pragma", "no-cache")
    return resp


# Initialize systems
system = TransportSystem()
predictor = TrafficPredictor()


def _path_distance_km(path: list[str]) -> float:
    if not path or len(path) < 2:
        return 0.0
    return round(system.graph.path_distance(path), 2)


def _estimate_metro_fare(distance_km: float) -> int:
    # Simple public-fare tiers for demo/education purposes.
    if distance_km <= 9:
        return 8
    if distance_km <= 16:
        return 10
    if distance_km <= 23:
        return 15
    return 20


def _estimate_bus_fare(distance_km: float) -> int:
    # Flat-ish bus fare approximation used for comparative UI guidance.
    if distance_km <= 8:
        return 7
    if distance_km <= 16:
        return 9
    return 12


def _transit_suggestions(path: list[str], distance_km: float) -> dict:
    if not path:
        return {"metro_lines": [], "bus_lines": [], "estimated_cost_egp": None, "recommended_mode": None}

    path_nodes = set(path)
    metro_lines = [line.id for line in METRO_LINES if len(path_nodes.intersection(set(line.stations))) >= 2]
    bus_lines = [route.id for route in BUS_ROUTES if len(path_nodes.intersection(set(route.stops))) >= 2]

    metro_fare = _estimate_metro_fare(distance_km) if metro_lines else None
    bus_fare = _estimate_bus_fare(distance_km) if bus_lines else None

    choices = []
    if metro_fare is not None:
        choices.append(("Metro", metro_fare))
    if bus_fare is not None:
        choices.append(("Bus", bus_fare))

    if choices:
        best_mode, best_cost = min(choices, key=lambda x: x[1])
    else:
        best_mode, best_cost = (None, None)

    return {
        "metro_lines": metro_lines,
        "bus_lines": bus_lines,
        "estimated_cost_egp": best_cost,
        "recommended_mode": best_mode,
    }


def _parse_blocked(spec: Optional[str]) -> Optional[Set[Tuple[str, str]]]:
    """Comma or newline-separated undirected edges, e.g. '3-10,F1-2'."""
    if not spec or not str(spec).strip():
        return None
    pairs: Set[Tuple[str, str]] = set()
    for part in str(spec).replace("\n", ",").split(","):
        part = part.strip()
        if not part or "-" not in part:
            continue
        left, right = part.split("-", 1)
        a, b = left.strip(), right.strip()
        if a and b and a in LOCATIONS and b in LOCATIONS:
            pairs.add((a, b))
            pairs.add((b, a))
        elif a and b:
            pairs.add((a, b))
            pairs.add((b, a))
    return pairs or None


def _congestion_segments(slot: str = "morning"):
    rows = []
    for rd in EXISTING_ROADS:
        key_fwd = f"{rd.src}-{rd.dst}"
        key_rev = f"{rd.dst}-{rd.src}"
        pat = TRAFFIC_PATTERNS.get(key_fwd) or TRAFFIC_PATTERNS.get(key_rev)
        flow = getattr(pat, slot, 1200) if pat else 1000
        cap = max(rd.capacity_vph, 1)
        ratio = min(1.0, flow / cap)
        a, b = LOCATIONS[rd.src], LOCATIONS[rd.dst]
        mx, my = (a.x + b.x) / 2, (a.y + b.y) / 2
        rows.append(
            {
                "from_id": rd.src,
                "to_id": rd.dst,
                "flow": flow,
                "capacity": cap,
                "ratio": round(ratio, 3),
                "lat": my,
                "lng": mx,
                "coords": [[a.y, a.x], [b.y, b.x]],
                "slot": slot,
            }
        )
    return rows


def _geo_snapshot() -> dict:
    """Same payload as GET /api/geo — inlined on first paint so dropdowns/map work offline from XHR blocking."""
    nodes = [
        {
            "id": loc.id,
            "name": loc.name,
            "kind": loc.kind,
            "population": loc.population,
            "lat": loc.y,
            "lng": loc.x,
        }
        for loc in LOCATIONS.values()
    ]
    edge_seen = set()
    roads_geo = []
    for rd in system.existing_roads:
        key = frozenset({rd.src, rd.dst})
        if key in edge_seen:
            continue
        edge_seen.add(key)
        a, b = LOCATIONS[rd.src], LOCATIONS[rd.dst]
        roads_geo.append(
            {
                "from_id": rd.src,
                "to_id": rd.dst,
                "existing": rd.existing,
                "coords": [[a.y, a.x], [b.y, b.x]],
            }
        )
    metro_geo = []
    for line in METRO_LINES:
        seq_coords = []
        for sid in line.stations:
            if sid in LOCATIONS:
                loc = LOCATIONS[sid]
                seq_coords.append([loc.y, loc.x])
        if len(seq_coords) >= 2:
            metro_geo.append(
                {
                    "id": line.id,
                    "name": line.name,
                    "daily_passengers": line.daily_passengers,
                    "coords": seq_coords,
                }
            )
    return {"nodes": nodes, "roads": roads_geo, "metro": metro_geo}


def _nodes_sorted_for_ui(geo: dict) -> list:
    def sort_key(n: dict) -> tuple:
        tid = str(n["id"])
        return (0, int(tid)) if tid.isdigit() else (1, tid)

    return sorted(geo["nodes"], key=sort_key)


def _neighborhood_nodes_only(sorted_nodes: list) -> list:
    return [n for n in sorted_nodes if str(n["id"]).isdigit()]


# =========================
# HOME (UI)
# =========================
@app.route("/")
def home():
    geo = _geo_snapshot()
    nodes_sorted = _nodes_sorted_for_ui(geo)
    nodes_hoods = _neighborhood_nodes_only(nodes_sorted)
    return render_template(
        "index.html",
        boot_geo=geo,
        nodes_sorted=nodes_sorted,
        nodes_hoods_only=nodes_hoods,
    )


@app.route("/api/health")
def api_health():
    return jsonify(ok=True, service="cairo-transport-lab", geo_nodes=len(LOCATIONS))


# =========================
# ROUTING (Dijkstra)
# =========================
@app.route("/route")
def route():
    source = request.args.get("source", "1")
    target = request.args.get("target", "3")
    slot = request.args.get("slot", "morning")
    algo = (request.args.get("algo", "dijkstra") or "dijkstra").lower()
    blocked = _parse_blocked(request.args.get("blocked"))

    if source == target:
        return jsonify(ok=False, error="Source and destination must differ."), 400
    try:
        if algo == "astar":
            # General A* for regular routing mode (independent from EMS-only endpoint).
            result = system.a_star_route(source, target, slot)
        else:
            result = system.standard_route(source, target, slot, closed_pairs=blocked)
    except KeyError as e:
        return jsonify(ok=False, error=str(e)), 400
    if not result.path:
        hint = " Try removing a road closure if edges are disconnected." if blocked else ""
        return jsonify(ok=False, error="No route found between these nodes for the chosen settings." + hint), 404
    distance_km = _path_distance_km(result.path)
    transit = _transit_suggestions(result.path, distance_km)
    return jsonify(
        ok=True,
        algo=algo,
        path=result.path,
        labels=[LOCATIONS[p].name for p in result.path],
        time=result.cost,
        distance_km=distance_km,
        transit=transit,
    )


# =========================
# EMERGENCY (A*)
# =========================
@app.route("/emergency")
def emergency():
    source = request.args.get("source", "12")
    target = request.args.get("target", "F9")
    slot = request.args.get("slot", "evening")

    if target not in {"F9", "F10"}:
        return jsonify(ok=False, error="Emergency target must be F9 or F10."), 400
    if source == target:
        return jsonify(ok=False, error="Origin and hospital must differ."), 400
    try:
        result = system.emergency_route(source, target, slot)
    except KeyError as e:
        return jsonify(ok=False, error=str(e)), 400
    if not result.path:
        return jsonify(ok=False, error="No reachable route to that facility."), 404
    distance_km = _path_distance_km(result.path)
    transit = _transit_suggestions(result.path, distance_km)
    return jsonify(
        ok=True,
        path=result.path,
        labels=[LOCATIONS[p].name for p in result.path],
        time=result.cost,
        distance_km=distance_km,
        transit=transit,
    )


# =========================
# ADAPTIVE ROUTING (Time-dependent)
# =========================
@app.route("/adaptive")
def adaptive():
    source = request.args.get("source", "1")
    target = request.args.get("target", "3")
    slot = request.args.get("slot", "morning")
    blocked = _parse_blocked(request.args.get("blocked"))

    if source == target:
        return jsonify(ok=False, error="Source and destination must differ."), 400
    try:
        if blocked:
            result = system.standard_route(source, target, slot, closed_pairs=blocked)
        else:
            result = system.adaptive_route(source, target, slot)
    except KeyError as e:
        return jsonify(ok=False, error=str(e)), 400
    if not result.path:
        return jsonify(ok=False, error="No route found."), 404
    distance_km = _path_distance_km(result.path)
    transit = _transit_suggestions(result.path, distance_km)
    return jsonify(
        ok=True,
        path=result.path,
        labels=[LOCATIONS[p].name for p in result.path],
        time=result.cost,
        distance_km=distance_km,
        transit=transit,
    )


@app.route("/api/geo")
def api_geo():
    """Coordinates follow GIS convention lat=Y from PDF columns."""
    g = _geo_snapshot()
    return jsonify(nodes=g["nodes"], roads=g["roads"], metro=g["metro"])


@app.route("/api/traffic_segments")
def api_traffic_segments():
    slot = request.args.get("slot", "morning")
    if slot not in ("morning", "afternoon", "evening", "night"):
        slot = "morning"
    return jsonify(ok=True, slot=slot, segments=_congestion_segments(slot))


@app.route("/api/bus_routes")
def api_bus_routes():
    routes = []
    palette = ["#0891b2", "#7c3aed", "#059669", "#d97706", "#db2777", "#475569"]
    for idx, bus in enumerate(BUS_ROUTES):
        seq = []
        for sid in bus.stops:
            if sid in LOCATIONS:
                loc = LOCATIONS[sid]
                seq.append([loc.y, loc.x])
        if len(seq) >= 2:
            routes.append(
                {
                    "id": bus.id,
                    "coords": seq,
                    "color": palette[idx % len(palette)],
                    "daily_passengers": bus.daily_passengers,
                }
            )
    return jsonify(ok=True, routes=routes)


@app.route("/api/compare_paths")
def api_compare_paths():
    """Dijkstra vs A* geometries for side-by-side map comparison."""
    source = request.args.get("source", "1")
    target = request.args.get("target", "3")
    slot = request.args.get("slot", "morning")
    blocked = _parse_blocked(request.args.get("blocked"))

    if source == target:
        return jsonify(ok=False, error="Pick two different nodes."), 400

    try:
        djk = system.standard_route(source, target, slot, closed_pairs=blocked)
        ast = system.a_star_route(source, target, slot)
    except KeyError as e:
        return jsonify(ok=False, error=str(e)), 400

    out = {"ok": True, "slot": slot, "dijkstra": None, "astar": None}
    if djk.path:
        out["dijkstra"] = {
            "path": djk.path,
            "labels": [LOCATIONS[p].name for p in djk.path],
            "coords": [[LOCATIONS[p].y, LOCATIONS[p].x] for p in djk.path],
            "time_minutes": djk.cost,
        }
    if ast.path:
        out["astar"] = {
            "path": ast.path,
            "labels": [LOCATIONS[p].name for p in ast.path],
            "coords": [[LOCATIONS[p].y, LOCATIONS[p].x] for p in ast.path],
            "time_minutes": ast.cost,
        }
    return jsonify(**out)


@app.route("/api/route_geom")
def api_route_geom():
    source = request.args.get("source", "1")
    target = request.args.get("target", "3")
    slot = request.args.get("slot", "morning")
    algo = (request.args.get("algo", "dijkstra") or "dijkstra").lower()
    blocked = _parse_blocked(request.args.get("blocked"))

    if source == target:
        return jsonify(ok=False, error="Source and destination must differ."), 400
    try:
        if algo == "astar_emergency":
            if target not in {"F9", "F10"}:
                return jsonify(ok=False, error="Emergency A* target must be F9 or F10."), 400
            result = system.emergency_route(source, target, slot)
        elif algo == "astar":
            result = system.a_star_route(source, target, slot)
        elif algo in ("adaptive", "time", "td"):
            result = (
                system.standard_route(source, target, slot, closed_pairs=blocked)
                if blocked
                else system.adaptive_route(source, target, slot)
            )
        else:
            result = system.standard_route(source, target, slot, closed_pairs=blocked)
    except KeyError as e:
        return jsonify(ok=False, error=str(e)), 400
    if not result.path:
        return jsonify(ok=False, error="No route found."), 404
    coords_ll = [[LOCATIONS[p].y, LOCATIONS[p].x] for p in result.path]
    return jsonify(
        ok=True,
        algo=algo,
        path=result.path,
        labels=[LOCATIONS[p].name for p in result.path],
        coords=coords_ll,
        time_minutes=result.cost,
    )


# =========================
# MST (Infrastructure Design)
# =========================
@app.route("/mst")
def mst():
    budget = float(request.args.get("budget", 1000.0))
    include_new = request.args.get("include_new", "true") == "true"

    result = system.build_mst(budget=budget, include_new=include_new)

    new_roads = [
        {"from": LOCATIONS[e.src].name, "to": LOCATIONS[e.dst].name, "cost": e.construction_cost_million}
        for e in result.selected_edges if not e.existing
    ]
    spans = [{"from_id": e.src, "to_id": e.dst} for e in result.selected_edges]
    return jsonify({
        "edges": len(result.selected_edges),
        "new_cost": result.construction_cost_million,
        "cost": result.score,
        "new_roads": new_roads,
        "spans": spans,
    })


# =========================
# PUBLIC TRANSIT (DP)
# =========================
@app.route("/transit")
def transit():
    buses = int(request.args.get("buses", 20))
    route = request.args.get("route", "ALL")

    result = system.bus_optimization(buses, specific_route=route)

    return jsonify({
        "served_passengers": result.estimated_served_passengers,
        "allocations": result.allocations
    })

# =========================
# ALGORITHM RACE (BONUS)
# =========================
@app.route("/compare_algorithms")
def compare_algorithms():
    source = request.args.get("source", "1")
    target = request.args.get("target", "13")

    if source == target:
        return jsonify(ok=False, error="Pick two different nodes."), 400

    race_stats = system.run_algorithm_race(source, target)
    return jsonify(ok=True, **race_stats)


# =========================
# MAINTENANCE (DP)
# =========================
@app.route("/maintenance")
def maintenance():
    budget = int(request.args.get("budget", 400))

    result = system.maintenance_optimization(budget)

    return jsonify({
        "total_benefit": result.total_benefit,
        "total_cost": result.total_cost,
        "roads": result.selected_roads
    })


# =========================
# TRAFFIC SIGNAL (Greedy)
# =========================
@app.route("/signal")
def signal():
    ns = int(request.args.get("ns", 50))
    ew = int(request.args.get("ew", 40))
    lt = int(request.args.get("lt", 10))
    ped = int(request.args.get("ped", 20))

    result = system.traffic_signal_plan(ns, ew, lt, ped)

    return jsonify({
        "cycle_length": result.cycle_length,
        "green_times": result.green_times
    })


@app.route("/signal_priority")
def signal_priority():
    slot = request.args.get("slot", "morning")
    if slot not in ("morning", "afternoon", "evening", "night"):
        slot = "morning"
    ranked = system.signal_priority_roads(slot)
    return jsonify(ok=True, slot=slot, roads=ranked)


# =========================
# EMERGENCY PREEMPTION (Greedy)
# =========================
@app.route("/preemption")
def preemption():
    tahrir = int(request.args.get("tahrir", 90))
    ramses = int(request.args.get("ramses", 120))
    qasr = int(request.args.get("qasr", 70))
    dokki = int(request.args.get("dokki", 50))
    result = system.preemption_plan(tahrir, ramses, qasr, dokki)

    return jsonify({
        "order": result.ordered_intersections,
        "saved_minutes": result.estimated_saved_minutes
    })


# =========================
# ML TRAFFIC PREDICTION
# =========================
@app.route("/predict")
def predict():
    slot = request.args.get("slot", "morning")
    capacity = int(request.args.get("capacity", 3000))
    condition = int(request.args.get("condition", 7))

    pred = predictor.predict(slot, capacity, condition)

    return jsonify({
        "prediction_vph": pred
    })


# =========================
# GRAPH VISUALIZATION
# =========================
def _fig_to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    buf.seek(0)
    png = buf.getvalue()
    plt.close(fig)
    return png


@app.route("/plot")
def plot():
    fig = system.plot_network(mode="existing")
    return Response(_fig_to_png(fig), mimetype="image/png")


# =========================
# ROUTE VISUALIZATION (matplotlib fallback — optional downloads)
# =========================
@app.route("/plot_route")
def plot_route():
    source = request.args.get("source", "1")
    target = request.args.get("target", "3")
    slot = request.args.get("slot", "morning")
    algo = (request.args.get("algo", "dijkstra") or "dijkstra").lower()

    try:
        if algo == "astar":
            result = system.emergency_route(source, target, slot)
        elif algo in ("adaptive", "time"):
            result = system.adaptive_route(source, target, slot)
        else:
            result = system.standard_route(source, target, slot)
    except KeyError:
        result = None

    if not result or not result.path:
        fig = system.plot_network(mode="existing")
    else:
        fig = system.plot_network(mode="existing", route=result.path)

    return Response(_fig_to_png(fig), mimetype="image/png")


@app.route("/plot_base64")
def plot_base64():
    """Legacy PNG base64 for clients expecting data URLs."""
    return base64.b64encode(_fig_to_png(system.plot_network(mode="existing")))


@app.route("/plot_route_base64")
def plot_route_base64():
    source = request.args.get("source", "1")
    target = request.args.get("target", "3")
    slot = request.args.get("slot", "morning")
    algo = (request.args.get("algo", "dijkstra") or "dijkstra").lower()
    try:
        if algo == "astar":
            result = system.emergency_route(source, target, slot)
        elif algo in ("adaptive", "time"):
            result = system.adaptive_route(source, target, slot)
        else:
            result = system.standard_route(source, target, slot)
    except KeyError:
        result = None
    if not result or not result.path:
        fig = system.plot_network(mode="existing")
    else:
        fig = system.plot_network(mode="existing", route=result.path)
    return base64.b64encode(_fig_to_png(fig))


# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    # Default 5000; use TRANSPORT_LAB_PORT=5050 if another app already uses 5000.
    host = os.environ.get("TRANSPORT_LAB_HOST", "127.0.0.1")
    port = int(os.environ.get("TRANSPORT_LAB_PORT", "5000"))
    print(f"\n>>> Cairo Transport Lab: http://{host}:{port}/\n")
    app.run(debug=True, host=host, port=port, use_reloader=True)