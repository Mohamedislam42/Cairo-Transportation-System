/**
 * Cairo Transport Lab — Leaflet + multi-basemap + overlays.
 */

const KIND_COLORS = {
    Residential: "#2563eb",
    Mixed: "#059669",
    Business: "#64748b",
    Industrial: "#d97706",
    Government: "#7c3aed",
    Airport: "#ea580c",
    "Transit Hub": "#0891b2",
    Education: "#9333ea",
    Tourism: "#db2777",
    Sports: "#0284c7",
    Commercial: "#0d9488",
    Medical: "#dc2626",
};

let mapInstance = null;
let baseLayerGroup = {}; // refs for switching
let currentBaseLayer = null;
let roadsLayer = null;
let metroLayer = null;
let trafficHeatLayer = null;
let busLayer = null;
let mstLayer = null;
let routeLayer = null;
let compareLayer = null;

let geoSnapshot = null;
let busGeoCache = null;
let lastMSTSpans = null;
let animateToken = 0;

function nodeRank(n) {
    if (/^\d+$/.test(n.id)) return [0, parseInt(n.id, 10)];
    return [1, n.id];
}

function cmpNodes(a, b) {
    const [ka, va] = nodeRank(a);
    const [kb, vb] = nodeRank(b);
    if (ka !== kb) return ka - kb;
    return typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb));
}

function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
}

function heatColor(ratio) {
    if (ratio < 0.5) return "#22c55e";
    if (ratio < 0.72) return "#eab308";
    if (ratio < 0.88) return "#f97316";
    return "#dc2626";
}

function buildLegend() {
    const host = document.getElementById("legend-kind-rows");
    if (!host) return;
    host.innerHTML = Object.entries(KIND_COLORS)
        .slice(0, 8)
        .map(([k, c]) => {
            return `<div class="d-flex align-items-center gap-2 mb-1"><span class="legend-dot" style="background:${c}"></span>${escapeHtml(k)}</div>`;
        })
        .join("") + `<div class="small text-muted mt-1">+ more types…</div>`;
}

function getBlockedRaw() {
    const ta = document.getElementById("blocked-roads");
    return (ta && ta.value.trim()) ? ta.value.trim() : "";
}

function getBlockedQS() {
    const b = getBlockedRaw();
    return b ? `&blocked=${encodeURIComponent(b)}` : "";
}

function invalidateMapHard() {
    if (!mapInstance) return;
    const run = () => {
        mapInstance.invalidateSize({ animate: false });
    };
    run();
    setTimeout(run, 80);
    setTimeout(run, 300);
    setTimeout(run, 800);
}

let _tileIssuesWarned = false;
function warnMapTilesBlocked() {
    if (_tileIssuesWarned) return;
    _tileIssuesWarned = true;
    showToast(
        "Basemap tiles are not loading (often Brave Shields or a firewall). Use the lion icon → Shields down for localhost, or switch basemap. Graph lines still draw on top.",
        "warning"
    );
}

function showToast(message, variant = "info") {
    const host = document.getElementById("viz-toast");
    if (!host) {
        alert(message);
        return;
    }
    const cls =
        variant === "danger"
            ? "danger"
            : variant === "warning"
              ? "warning"
              : variant === "success"
                ? "success"
                : "secondary";
    host.innerHTML = `<div class="alert alert-${cls} alert-dismissible py-2 px-3 mb-0 shadow-sm small fade show" role="alert">
      ${escapeHtml(message)}
      <button type="button" class="btn-close btn-sm" data-bs-dismiss="alert" aria-label="Close"></button>
    </div>`;
}

function clearVizToast() {
    const host = document.getElementById("viz-toast");
    if (host) host.innerHTML = "";
}

function ensureMap() {
    if (mapInstance) return;
    const el = document.getElementById("real-map");
    if (!el) return;

    mapInstance = L.map(el, { scrollWheelZoom: true, zoomControl: true }).setView([30.05, 31.33], 10);

    /* Real-world tile providers (XYZ, attribution required). */
    const carto = L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        {
            attribution: '&copy; OSM &copy; <a href="https://carto.com/">CARTO</a>',
            subdomains: "abcd",
            maxZoom: 20,
        }
    );
    const positron = L.tileLayer(
        "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        {
            attribution: '&copy; OSM &copy; CARTO',
            subdomains: "abcd",
            maxZoom: 20,
        }
    );
    const osm = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        maxZoom: 19,
        attribution: '&copy; <a href="https://openstreetmap.org">OpenStreetMap</a>',
    });
    /* Esri World Imagery — satellite-style basemap */
    const sat = L.tileLayer(
        "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        { maxZoom: 19, attribution: "Tiles © Esri" }
    );

    [osm, carto, positron, sat].forEach((lyr) => {
        lyr.on("tileerror", warnMapTilesBlocked);
    });

    /* OpenStreetMap first — least likely to be fingerprint-blocked vs Carto. */
    osm.addTo(mapInstance);
    currentBaseLayer = osm;

    baseLayerGroup = {
        osm_standard: osm,
        carto_voyager: carto,
        carto_light: positron,
        satellite: sat,
    };

    const bs = document.getElementById("basemap-select");
    if (bs) {
        bs.innerHTML = "";
        [
            ["osm_standard", "OpenStreetMap (default)"],
            ["carto_voyager", "Streets (Carto Voyager)"],
            ["carto_light", "Light (Carto)"],
            ["satellite", "Satellite (Esri)"],
        ].forEach(([val, lbl]) => bs.add(new Option(lbl, val)));
        bs.value = "osm_standard";
        bs.addEventListener("change", () => {
            mapInstance.removeLayer(currentBaseLayer);
            currentBaseLayer = baseLayerGroup[bs.value] || osm;
            mapInstance.addLayer(currentBaseLayer);
            currentBaseLayer.bringToBack();
            bringOverlaysFront();
        });
    }

    roadsLayer = L.layerGroup().addTo(mapInstance);
    metroLayer = L.layerGroup().addTo(mapInstance);
    trafficHeatLayer = L.layerGroup(); // toggle add
    busLayer = L.layerGroup(); // toggle add
    mstLayer = L.featureGroup(); // getBounds + layer control; same API as layerGroup
    routeLayer = L.layerGroup().addTo(mapInstance);
    compareLayer = L.layerGroup(); // toggled after compare

    L.control.layers(
        {},
        {
            "Road graph": roadsLayer,
            Metro: metroLayer,
            "Traffic heat": trafficHeatLayer,
            "Bus overlays": busLayer,
            "MST outline": mstLayer,
            "Compare paths": compareLayer,
            "Active route": routeLayer,
        },
        { collapsed: true, position: "topright" }
    ).addTo(mapInstance);

    L.control.scale({ metric: true, imperial: false, position: "bottomleft" }).addTo(mapInstance);

    mapInstance.zoomControl.setPosition("topleft");

    mapInstance.whenReady(() => invalidateMapHard());
    try {
        const mapEl = document.getElementById("real-map");
        if (mapEl && typeof ResizeObserver !== "undefined") {
            new ResizeObserver(() => invalidateMapHard()).observe(mapEl);
        }
    } catch (_) {
        /* ignore */
    }

    window.addEventListener("resize", () => invalidateMapHard());
}

function redrawFromGeo(showMetro) {
    ensureMap();
    if (!geoSnapshot) return;
    roadsLayer.clearLayers();

    geoSnapshot.roads.forEach((r) => {
        L.polyline(r.coords, {
            color: "#1e293b",
            weight: 2,
            opacity: 0.35,
            lineCap: "round",
            lineJoin: "round",
        }).addTo(roadsLayer);
    });

    metroLayer.clearLayers();
    if (showMetro && geoSnapshot.metro) {
        geoSnapshot.metro.forEach((m) => {
            L.polyline(m.coords, {
                color: "#6d28d9",
                weight: 5,
                opacity: 0.85,
                dashArray: "10 14",
                lineCap: "round",
            })
                .bindPopup(
                    `<strong>${escapeHtml(m.id)}</strong><br>${escapeHtml(m.name)}<br>${m.daily_passengers.toLocaleString()} pax/day`
                )
                .addTo(metroLayer);
        });
    }
}

let markersLeafGroup = null;

/** LayerGroup / some builds lack bringToFront; circleMarker & paths have it. */
function safeBringToFront(layer) {
    if (!layer) return;
    try {
        if (typeof layer.bringToFront === "function") {
            layer.bringToFront();
            return;
        }
    } catch (_) {
        /* ignore */
    }
    if (typeof layer.eachLayer === "function") {
        layer.eachLayer((ly) => {
            try {
                if (typeof ly.bringToFront === "function") ly.bringToFront();
            } catch (_) {
                /* ignore */
            }
        });
    }
}

function bringOverlaysFront() {
    safeBringToFront(roadsLayer);
    safeBringToFront(trafficHeatLayer);
    safeBringToFront(metroLayer);
    safeBringToFront(busLayer);
    safeBringToFront(mstLayer);
    safeBringToFront(compareLayer);
    safeBringToFront(routeLayer);
    safeBringToFront(markersLeafGroup);
}

function redrawMarkers(nodes) {
    ensureMap();
    if (!markersLeafGroup) markersLeafGroup = L.featureGroup().addTo(mapInstance);
    else markersLeafGroup.clearLayers();

    const list = nodes || (geoSnapshot && geoSnapshot.nodes);
    if (!list) return;

    list.forEach((n) => {
        const fill = KIND_COLORS[n.kind] || "#334155";
        const r = Math.max(6, n.population > 0 ? Math.sqrt(n.population / 2200) : 8);
        L.circleMarker([n.lat, n.lng], {
            radius: r,
            color: "#0f172a",
            weight: 1.2,
            fillColor: fill,
            fillOpacity: 0.9,
        })
            .bindPopup(
                `<strong>${escapeHtml(n.id)}</strong> ${escapeHtml(n.name)}<br><span class="text-muted">${escapeHtml(n.kind)}</span>${
                    n.population ? `<br>${n.population.toLocaleString()} residents` : ""
                }`
            )
            .addTo(markersLeafGroup);
    });

    safeBringToFront(markersLeafGroup);
    const b = markersLeafGroup.getBounds();
    if (b.isValid() && !window.__didInitialMapFit) {
        mapInstance.fitBounds(b.pad(0.1));
        window.__didInitialMapFit = true;
    }
}

async function loadTrafficHeat() {
    ensureMap();
    trafficHeatLayer.clearLayers();
    const slot = document.getElementById("slot")?.value || "morning";
    try {
        const res = await fetch(`/api/traffic_segments?slot=${encodeURIComponent(slot)}`);
        const data = await res.json();
        if (!data.ok || !data.segments) throw new Error("Bad traffic payload");
        data.segments.forEach((seg) => {
            L.polyline(seg.coords, {
                color: heatColor(seg.ratio),
                weight: 7,
                opacity: 0.75,
                lineCap: "round",
                lineJoin: "round",
            })
                .bindTooltip(`Flow ${seg.flow.toLocaleString()}/${seg.capacity}<br>${(seg.ratio * 100).toFixed(0)}% saturation`, {
                    sticky: true,
                })
                .addTo(trafficHeatLayer);
        });
        if (!mapInstance.hasLayer(trafficHeatLayer)) trafficHeatLayer.addTo(mapInstance);
        const hint = document.getElementById("traffic-slot-hint");
        if (hint) {
            hint.classList.remove("d-none");
            hint.innerHTML = `<i class="fa-solid fa-chart-area me-1"></i>Heat for <strong>${escapeHtml(slot)}</strong>`;
        }
        bringOverlaysFront();
    } catch (e) {
        showToast(String(e.message || e), "warning");
    }
}

async function loadBusLines() {
    ensureMap();
    busLayer.clearLayers();
    try {
        if (!busGeoCache) {
            const res = await fetch("/api/bus_routes");
            busGeoCache = await res.json();
        }
        (busGeoCache.routes || []).forEach((route) => {
            L.polyline(route.coords, { color: route.color, weight: 4, opacity: 0.82, dashArray: "6 10" })
                .bindPopup(`<strong>${escapeHtml(route.id)}</strong> · ${route.daily_passengers.toLocaleString()} pax/day`)
                .addTo(busLayer);
        });
        busLayer.addTo(mapInstance);
    } catch (_) {
        showToast("Could not load bus geometries.", "warning");
    }
}

async function loadGeoAndRender(options = {}) {
    const showMetro = document.getElementById("toggle-metro")?.checked ?? true;
    ensureMap();
    try {
        const res = await fetch("/api/geo");
        if (!res.ok) throw new Error("Network geo load failed.");
        geoSnapshot = await res.json();
        redrawFromGeo(showMetro);
        redrawMarkers(geoSnapshot.nodes);
        populateDropdowns(geoSnapshot.nodes);
        if (options.keepRoute !== true) {
            routeLayer.clearLayers();
            compareLayer.clearLayers();
        }
        if (document.getElementById("toggle-traffic")?.checked) await loadTrafficHeat();
        syncOverlayToggles();
    } catch (e) {
        showToast(String(e.message || e), "danger");
    }
}

function syncOverlayToggles() {
    ensureMap();
    if (document.getElementById("toggle-traffic")?.checked) trafficHeatLayer.addTo(mapInstance);
    else mapInstance.removeLayer(trafficHeatLayer);
    if (document.getElementById("toggle-bus")?.checked) {
        loadBusLines();
    } else mapInstance.removeLayer(busLayer);
}

/** Fills selects only when empty so server-rendered <option>s stay (Brave/JS-safe). */
function populateDropdowns(nodes) {
    if (!nodes || !nodes.length) return;
    const sorted = [...nodes].sort(cmpNodes);
    ["source", "target"].forEach((id) => {
        const sel = document.getElementById(id);
        if (!sel || sel.options.length > 0) return;
        sorted.forEach((n) => sel.add(new Option(`${n.id} · ${n.name}`, n.id)));
    });
    const emSource = document.getElementById("em_source");
    if (emSource && emSource.options.length === 0) {
        sorted.filter((n) => /^\d+$/.test(n.id)).forEach((n) => emSource.add(new Option(`${n.id} · ${n.name}`, n.id)));
    }
}

window.onload = () => {
    try {
        buildLegend();
        ensureMap();

        fetch("/api/health")
            .then((r) => (r.ok ? r.json() : Promise.reject()))
            .then((d) => {
                if (!d.ok) showToast("API health check failed.", "warning");
            })
            .catch(() => {
                showToast("Cannot reach /api/health — start Flask from the project folder (app.py) and use the URL it prints.", "danger");
            });

        if (window.__BOOT_GEO?.nodes?.length) {
            geoSnapshot = window.__BOOT_GEO;
            populateDropdowns(geoSnapshot.nodes);
            window.__didInitialMapFit = false;
            redrawFromGeo(document.getElementById("toggle-metro")?.checked ?? true);
            redrawMarkers(geoSnapshot.nodes);
            invalidateMapHard();
            if (document.getElementById("toggle-traffic")?.checked) loadTrafficHeat().catch(() => {});
            syncOverlayToggles();
        } else {
            loadGeoAndRender();
        }
    } catch (err) {
        console.error(err);
        showToast(`Page script error: ${err && err.message ? err.message : err}`, "danger");
    }
};

function refreshMapLayout() {
    invalidateMapHard();
}

function setModuleTitles(text) {
    const a = document.getElementById("module-title");
    const b = document.getElementById("module-title-mobile");
    if (a) a.textContent = text;
    if (b) b.textContent = text;
}

function showTab(tabId, el) {
    document.querySelectorAll(".tab-content").forEach((t) => t.classList.add("d-none"));
    const pane = document.getElementById(tabId);
    if (pane) pane.classList.remove("d-none");

    document.querySelectorAll(".sidebar .nav-btn").forEach((b) => b.classList.remove("active"));
    if (el) el.classList.add("active");

    if (tabId === "routing") setModuleTitles("Standard routing");
    else if (tabId === "emergency") setModuleTitles("Emergency response");
    else setModuleTitles("Optimization suite");

    refreshMapLayout();
}

document.addEventListener("change", async (e) => {
    if (!e.target) return;
    if (e.target.id === "toggle-metro") {
        if (geoSnapshot) redrawFromGeo(e.target.checked);
    }
    if (e.target.id === "toggle-traffic") {
        ensureMap();
        if (e.target.checked) {
            await loadTrafficHeat();
        } else if (mapInstance?.hasLayer(trafficHeatLayer)) {
            mapInstance.removeLayer(trafficHeatLayer);
        }
        const hint = document.getElementById("traffic-slot-hint");
        if (hint && !e.target.checked) hint.classList.add("d-none");
    }
    if (e.target.id === "toggle-bus") {
        ensureMap();
        if (e.target.checked) await loadBusLines();
        else if (mapInstance?.hasLayer(busLayer)) mapInstance.removeLayer(busLayer);
    }
    if (e.target.id === "slot" && document.getElementById("toggle-traffic")?.checked) {
        await loadTrafficHeat();
    }
});

/** Side-by-side Dijkstra vs A* “race”: both routes grow in parallel on compareLayer */
function animateCompareRace(dijkCoords, astarCoords, metaDijk, metaAstar) {
    const token = ++animateToken;
    compareLayer.clearLayers();

    let lineD = null;
    let lineA = null;
    const hasD = dijkCoords && dijkCoords.length >= 2;
    const hasA = astarCoords && astarCoords.length >= 2;

    if (hasD) {
        const dPop = metaDijk
            ? `Dijkstra · ${metaDijk.time_minutes} min<br>${escapeHtml((metaDijk.labels || []).join(" → "))}`
            : "Dijkstra";
        lineD = L.polyline([], {
            color: "#0d9488",
            weight: 9,
            opacity: 0.92,
            lineCap: "round",
            lineJoin: "round",
        })
            .bindPopup(dPop)
            .addTo(compareLayer);
    }
    if (hasA) {
        const aPop = metaAstar
            ? `A* · ${metaAstar.time_minutes} min<br>${escapeHtml((metaAstar.labels || []).join(" → "))}`
            : "A*";
        lineA = L.polyline([], {
            color: "#dc2626",
            weight: 6,
            opacity: 0.92,
            dashArray: "10 14",
            lineCap: "round",
            lineJoin: "round",
        })
            .bindPopup(aPop)
            .addTo(compareLayer);
    }

    const maxLen = Math.max(hasD ? dijkCoords.length : 0, hasA ? astarCoords.length : 0);
    const dur = Math.min(3400, 380 + maxLen * 85);
    const t0 = performance.now();

    return new Promise((resolve) => {
        function frame(now) {
            if (token !== animateToken) {
                resolve();
                return;
            }
            const p = Math.min(1, (now - t0) / dur);
            if (lineD && hasD) {
                const upto = Math.max(2, Math.ceil(1 + p * (dijkCoords.length - 1)));
                lineD.setLatLngs(dijkCoords.slice(0, upto));
            }
            if (lineA && hasA) {
                const upto = Math.max(2, Math.ceil(1 + p * (astarCoords.length - 1)));
                lineA.setLatLngs(astarCoords.slice(0, upto));
            }
            if (p < 1) requestAnimationFrame(frame);
            else {
                const b = [];
                if (hasD) b.push(L.polyline(dijkCoords).getBounds());
                if (hasA) b.push(L.polyline(astarCoords).getBounds());
                if (b.length === 1) mapInstance.fitBounds(b[0].pad(0.14));
                if (b.length === 2) mapInstance.fitBounds(b[0].extend(b[1]).pad(0.14));
                bringOverlaysFront();
                resolve();
            }
        }
        requestAnimationFrame(frame);
    });
}

function animatePolyline(coords, color, layerGroup) {
    const token = ++animateToken;
    layerGroup.clearLayers();
    const line = L.polyline([], {
        color,
        weight: 8,
        opacity: 0.93,
        lineCap: "round",
        lineJoin: "round",
    }).addTo(layerGroup);

    const dur = Math.min(2000, 320 + coords.length * 100);
    const t0 = performance.now();

    return new Promise((resolve) => {
        function frame(now) {
            if (token !== animateToken) {
                resolve();
                return;
            }
            const p = Math.min(1, (now - t0) / dur);
            const upto = Math.max(2, Math.ceil(1 + p * (coords.length - 1)));
            line.setLatLngs(coords.slice(0, upto));
            if (p < 1) requestAnimationFrame(frame);
            else {
                const bb = line.getBounds();
                if (bb.isValid()) mapInstance.fitBounds(bb.pad(0.15));
                resolve();
            }
        }
        requestAnimationFrame(frame);
    });
}

async function drawRouteOnMap(algo, options = {}) {
    ensureMap();
    let source, target, slot;
    if (algo === "astar_emergency") {
        source = document.getElementById("em_source").value;
        target = document.getElementById("em_target").value;
        slot = document.getElementById("em_slot").value;
    } else {
        source = document.getElementById("source").value;
        target = document.getElementById("target").value;
        slot = document.getElementById("slot").value;
    }

    const blocked = options.skipBlocked ? "" : getBlockedQS();
    if (compareLayer && mapInstance.hasLayer(compareLayer)) mapInstance.removeLayer(compareLayer);
    compareLayer.clearLayers();

    const uri = `/api/route_geom?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&slot=${encodeURIComponent(
        slot
    )}&algo=${encodeURIComponent(algo)}${blocked}`;

    const res = await fetch(uri);
    const data = await res.json();
    if (!res.ok || data.ok === false) {
        showToast(data.error || "Could not draw route.", "warning");
        return false;
    }
    const animate = document.getElementById("animate-route")?.checked && algo !== "compare";
    compareLayer.clearLayers();
    mapInstance.removeLayer(compareLayer);

    if (algo === "astar" || algo === "astar_emergency") {
        if (animate) await animatePolyline(data.coords, "#dc2626", routeLayer);
        else {
            routeLayer.clearLayers();
            L.polyline(data.coords, {
                color: "#b91c1c",
                weight: 8,
                opacity: 0.95,
                lineCap: "round",
            })
                .bindPopup(`${escapeHtml(data.labels.join(" → "))}<br><strong>${data.time_minutes} min</strong>`)
                .addTo(routeLayer);
            const bb = L.polyline(data.coords).getBounds();
            if (bb.isValid()) mapInstance.fitBounds(bb.pad(0.15));
        }
    } else {
        if (animate) await animatePolyline(data.coords, "#0d9488", routeLayer);
        else {
            routeLayer.clearLayers();
            L.polyline(data.coords, {
                color: "#0f766e",
                weight: 8,
                opacity: 0.95,
                lineCap: "round",
            })
                .bindPopup(`${escapeHtml(data.labels.join(" → "))}<br><strong>${data.time_minutes} min</strong>`)
                .addTo(routeLayer);
            const bb = L.polyline(data.coords).getBounds();
            if (bb.isValid()) mapInstance.fitBounds(bb.pad(0.15));
        }
    }
    return true;
}

function clearRouteLayers() {
    animateToken++;
    routeLayer.clearLayers();
    compareLayer.clearLayers();
    mapInstance.removeLayer(compareLayer);
    showToast("Route layers cleared.", "secondary");
}

async function comparePathsOnMap(skipToast) {
    ensureMap();
    animateToken++;
    const source = document.getElementById("source").value;
    const target = document.getElementById("target").value;
    const slot = document.getElementById("slot").value;

    compareLayer.clearLayers();
    compareLayer.addTo(mapInstance);
    routeLayer.clearLayers();

    const uri = `/api/compare_paths?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}&slot=${encodeURIComponent(
        slot
    )}${getBlockedQS()}`;
    const res = await fetch(uri);
    const data = await res.json();
    if (data.ok === false) {
        showToast(data.error || "Compare failed", "danger");
        return;
    }
    if (!data.dijkstra && !data.astar) {
        showToast("No valid paths returned for comparison.", "warning");
        return;
    }

    const raceAnim = document.getElementById("animate-route")?.checked;

    if (raceAnim) {
        await animateCompareRace(data.dijkstra?.coords, data.astar?.coords, data.dijkstra, data.astar);
        if (!skipToast)
            showToast("Race animation: Dijkstra (solid green) vs A* (red dashed).", "success");
        return;
    }

    let bounds = [];

    if (data.dijkstra && data.dijkstra.coords?.length >= 2) {
        L.polyline(data.dijkstra.coords, { color: "#0d9488", weight: 9, opacity: 0.9, lineCap: "round" })
            .bindPopup(`Dijkstra · ${data.dijkstra.time_minutes} min<br>${escapeHtml(data.dijkstra.labels.join(" → "))}`)
            .addTo(compareLayer);
        bounds.push(L.polyline(data.dijkstra.coords).getBounds());
    }
    if (data.astar && data.astar.coords?.length >= 2) {
        L.polyline(data.astar.coords, {
            color: "#dc2626",
            weight: 6,
            opacity: 0.9,
            dashArray: "10 14",
            lineCap: "round",
        })
            .bindPopup(`A* · ${data.astar.time_minutes} min<br>${escapeHtml(data.astar.labels.join(" → "))}`)
            .addTo(compareLayer);
        bounds.push(L.polyline(data.astar.coords).getBounds());
    }
    if (bounds.length === 1) mapInstance.fitBounds(bounds[0].pad(0.15));
    if (bounds.length === 2) {
        let box = bounds[0];
        box = box.extend(bounds[1]);
        mapInstance.fitBounds(box.pad(0.14));
    }
    bringOverlaysFront();
    if (!skipToast) showToast("Compared paths plotted (green solid vs red dashed).", "success");
}

function plotBothFromRaceModal() {
    comparePathsOnMap(true);
    const modalEl = document.getElementById("raceModal");
    const inst = bootstrap.Modal.getInstance(modalEl);
    if (inst) inst.hide();
    showToast("Compared paths plotted on map.", "success");
}

async function runRoute() {
    const s = document.getElementById("source").value;
    const t = document.getElementById("target").value;
    const slot = document.getElementById("slot").value;
    const modeSel = document.getElementById("routing-algo");
    const routingMode = modeSel?.value === "adaptive" ? "adaptive" : modeSel?.value === "astar" ? "astar" : "dijkstra";
    const resDiv = document.getElementById("routeResult");
    resDiv.classList.remove("d-none");
    resDiv.innerHTML = `<span class="text-muted">Computing…</span>`;
    // Single-route actions should never leave compare state visible.
    clearVizToast();
    if (compareLayer && mapInstance?.hasLayer(compareLayer)) mapInstance.removeLayer(compareLayer);
    compareLayer?.clearLayers();

    const qp = `source=${encodeURIComponent(s)}&target=${encodeURIComponent(t)}&slot=${encodeURIComponent(slot)}${getBlockedQS()}`;
    const url = routingMode === "adaptive" ? `/adaptive?${qp}` : `/route?${qp}&algo=${encodeURIComponent(routingMode)}`;

    const res = await fetch(url);
    const data = await res.json();
    if (!res.ok || data.ok === false) {
        resDiv.innerHTML = `<span class="text-danger">${escapeHtml(data.error || "Failed.")}</span>`;
        showToast(data.error || "Routing failed", "danger");
        return;
    }
    const algoLabel =
        routingMode === "adaptive" ? "Time-slot routing" : routingMode === "astar" ? "A* (heuristic)" : "Standard (Dijkstra)";
    const blockNote = getBlockedRaw() ? "\n(with road closures)" : "";
    resDiv.innerHTML =
        `<strong>${algoLabel}</strong>${blockNote}\n` +
        `${data.labels.join(" → ")}\n\n<strong>Estimated time</strong>\n${data.time} minutes` +
        `\nDistance\n${(data.distance_km ?? 0).toFixed(2)} km` +
        renderTransitHint(data);
    compareLayer.clearLayers();
    await drawRouteOnMap(routingMode);
}

function showRouteOnMap() {
    const v = document.getElementById("routing-algo")?.value;
    const mode = v === "adaptive" ? "adaptive" : v === "astar" ? "astar" : "dijkstra";
    clearVizToast();
    if (compareLayer && mapInstance?.hasLayer(compareLayer)) mapInstance.removeLayer(compareLayer);
    compareLayer?.clearLayers();
    drawRouteOnMap(mode);
}

async function runEmergency() {
    const s = document.getElementById("em_source").value;
    const t = document.getElementById("em_target").value;
    const slot = document.getElementById("em_slot").value;
    const resDiv = document.getElementById("emergencyResult");
    resDiv.classList.remove("d-none");
    resDiv.innerHTML = `<span class="text-muted">Dispatching…</span>`;
    clearVizToast();
    if (compareLayer && mapInstance?.hasLayer(compareLayer)) mapInstance.removeLayer(compareLayer);
    compareLayer?.clearLayers();

    const res = await fetch(`/emergency?source=${encodeURIComponent(s)}&target=${encodeURIComponent(t)}&slot=${encodeURIComponent(slot)}`);
    const data = await res.json();
    if (!res.ok || data.ok === false) {
        resDiv.innerHTML = `<span class="text-danger">${escapeHtml(data.error || "Failed.")}</span>`;
        showToast(data.error || "Emergency routing failed", "danger");
        return;
    }
    resDiv.innerHTML =
        `Dispatch (A*)\n${data.labels.join(" → ")}\n\nEstimated\n${data.time} minutes` +
        `\nDistance\n${(data.distance_km ?? 0).toFixed(2)} km`;
    await drawRouteOnMap("astar_emergency");
}

function showEmergencyOnMap() {
    clearVizToast();
    if (compareLayer && mapInstance?.hasLayer(compareLayer)) mapInstance.removeLayer(compareLayer);
    compareLayer?.clearLayers();
    drawRouteOnMap("astar_emergency");
}

function renderTransitHint(data) {
    const t = data?.transit;
    if (!t) return "";
    const metro = t.metro_lines?.length ? t.metro_lines.join(", ") : "none matched";
    const bus = t.bus_lines?.length ? t.bus_lines.join(", ") : "none matched";
    const mode = t.recommended_mode || "N/A";
    const cost = t.estimated_cost_egp != null ? `${t.estimated_cost_egp} EGP` : "N/A";
    return (
        `\n\nTransit suggestion (heuristic)\n` +
        `Metro lines: ${metro}\n` +
        `Bus lines: ${bus}\n` +
        `Recommended mode: ${mode}\n` +
        `Estimated ride cost: ${cost}`
    );
}

function loadGraph() {
    loadGeoAndRender({ keepRoute: false });
    lastMSTSpans = null;
    mstLayer.clearLayers();
}

function outlineMSTOnMap() {
    ensureMap();
    if (!lastMSTSpans || !lastMSTSpans.length) {
        showToast("Run MST first — nothing to outline yet.", "warning");
        return;
    }
    if (!geoSnapshot) {
        showToast("Map data not loaded.", "warning");
        return;
    }
    mstLayer.clearLayers();
    lastMSTSpans.forEach(({ from_id, to_id }) => {
        const a = geoSnapshot.nodes.find((n) => n.id === from_id);
        const b = geoSnapshot.nodes.find((n) => n.id === to_id);
        if (!a || !b) return;
        L.polyline(
            [
                [a.lat, a.lng],
                [b.lat, b.lng],
            ],
            { color: "#15803d", weight: 5, dashArray: "4 10", opacity: 0.9 }
        ).addTo(mstLayer);
    });
    mstLayer.addTo(mapInstance);
    const bds = mstLayer.getBounds();
    if (bds.isValid()) mapInstance.fitBounds(bds.pad(0.08));
    showToast("MST edges highlighted.", "success");
}

function runDynamicMST() {
    const budget = document.getElementById("mst-budget").value;
    const includeNew = document.getElementById("include-new-roads").checked;
    const resDiv = document.getElementById("mstResult");
    resDiv.innerHTML = `<span class="text-muted">Computing…</span>`;
    resDiv.classList.remove("d-none");

    fetch(`/mst?budget=${budget}&include_new=${includeNew}`)
        .then((res) => res.json())
        .then((data) => {
            lastMSTSpans = data.spans || null;
            let newRoadsHtml = "";
            if (data.new_roads && data.new_roads.length > 0) {
                newRoadsHtml = "\n" + data.new_roads.map((r) => `  • ${r.from} ↔ ${r.to} (${r.cost}M EGP)`).join("\n");
            } else {
                newRoadsHtml = "\nNo new construction at this budget.";
            }
            resDiv.innerHTML =
                `Spanning edges: ${data.edges}\nNew spend: ${Number(data.new_cost).toFixed(2)} M EGP\nScore: ${data.cost}` + newRoadsHtml;
        })
        .catch(() => {
            resDiv.innerHTML = `<span class="text-danger">MST request failed.</span>`;
        });
}

function runDynamicTransit() {
    const buses = document.getElementById("buses").value;
    const route = document.getElementById("transit-route")?.value || "ALL";
    const resDiv = document.getElementById("transitResult");
    resDiv.innerHTML = `<span class="text-muted">Optimizing…</span>`;
    resDiv.classList.remove("d-none");

    fetch(`/transit?buses=${buses}&route=${route}`)
        .then((res) => res.json())
        .then((data) => {
            const lines = Object.entries(data.allocations)
                .map(([k, v]) => `${k}: ${v} buses`)
                .join("\n");
            resDiv.innerHTML = `Passengers served (est.)\n${data.served_passengers.toLocaleString()}\n\n${lines}`;
        })
        .catch(() => {
            resDiv.innerHTML = `<span class="text-danger">Transit failed.</span>`;
        });
}

function runMaintenance() {
    const budget = document.getElementById("maint-budget").value;
    const resDiv = document.getElementById("maintResult");
    resDiv.classList.remove("d-none");
    resDiv.innerHTML = `<span class="text-muted">Planning…</span>`;
    fetch(`/maintenance?budget=${encodeURIComponent(budget)}`)
        .then((r) => r.json())
        .then((data) => {
            const roads = (data.roads || []).map(([a, b]) => `  ${a}–${b}`).join("\n");
            resDiv.innerHTML = `Total benefit (score) ${data.total_benefit}\nBudget spent ${data.total_cost} / ${budget} million EGP\n\nRepairs:\n${roads || "(none)"}`;
        })
        .catch(() => {
            resDiv.innerHTML = `<span class="text-danger">Failed.</span>`;
        });
}

function runPredict() {
    const slot = document.getElementById("pred-slot").value;
    const capacity = document.getElementById("pred-cap").value;
    const condition = document.getElementById("pred-cond").value;
    const resDiv = document.getElementById("predResult");
    resDiv.classList.remove("d-none");
    resDiv.innerHTML = `<span class="text-muted">Predicting…</span>`;
    fetch(`/predict?slot=${encodeURIComponent(slot)}&capacity=${encodeURIComponent(capacity)}&condition=${encodeURIComponent(condition)}`)
        .then((r) => r.json())
        .then((data) => {
            resDiv.innerHTML = `Forecast\n~${data.prediction_vph.toLocaleString()} vph\n(RandomForest)`;
        })
        .catch(() => {
            resDiv.innerHTML = `<span class="text-danger">Failed.</span>`;
        });
}

function runSignal() {
    const ns = document.getElementById("ns").value;
    const ew = document.getElementById("ew").value;
    const lt = document.getElementById("lt").value;
    const ped = document.getElementById("ped").value;
    const resultDiv = document.getElementById("signalResult");
    resultDiv.classList.remove("d-none");
    resultDiv.innerHTML = `<span class="text-muted">Optimizing…</span>`;

    Promise.all([
        fetch(`/signal?ns=${ns}&ew=${ew}&lt=${lt}&ped=${ped}`).then((r) => r.json()),
        fetch(`/preemption`).then((r) => r.json()),
    ])
        .then(([sigData, preData]) => {
            const gt = sigData.green_times;
            const cycle = sigData.cycle_length;
            const lanes = [
                { key: "North-South", label: "N–S", color: "#198754", queue: ns },
                { key: "East-West", label: "E–W", color: "#0d6efd", queue: ew },
                { key: "Left-Turn", label: "Left", color: "#6f42c1", queue: lt },
                { key: "Pedestrian", label: "Ped", color: "#fd7e14", queue: ped },
            ];
            const rows = lanes
                .map((l) => {
                    const t = gt[l.key];
                    const pct = Math.round((t / cycle) * 100);
                    return `${l.label} queue ${l.queue}: ${t}s (${pct}%)\n`;
                })
                .join("");
            resultDiv.innerHTML = `Cycle ${cycle}s\n${rows}\nPreempt: ${preData.order.join(" → ")} (~${preData.saved_minutes} min)`;
        })
        .catch(() => {
            resultDiv.innerHTML = `<span class="text-danger">Signal planner failed.</span>`;
        });
}

function raceAlgorithms() {
    const source = document.getElementById("source")?.value ?? "1";
    const target = document.getElementById("target")?.value ?? "13";
    fetch(`/compare_algorithms?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`)
        .then((r) => r.json())
        .then((data) => {
            if (data.ok === false) {
                showToast(data.error || "Bench failed", "danger");
                return;
            }
            document.getElementById("race-d-time").textContent = `${data.dijkstra_time} ms`;
            document.getElementById("race-a-time").textContent = `${data.astar_time} ms`;
            document.getElementById("race-d-nodes").textContent = `${data.dijkstra_nodes}`;
            document.getElementById("race-a-nodes").textContent = `${data.astar_nodes}`;
            document.getElementById("race-pair").textContent = `${source} → ${target}`;
            bootstrap.Modal.getOrCreateInstance(document.getElementById("raceModal")).show();
        })
        .catch(() => showToast("Bench failed.", "danger"));
}
