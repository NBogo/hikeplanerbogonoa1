<script>
    import { browser, dev } from "$app/environment";
    import { onMount } from "svelte";

    let url = dev ? "http://localhost:5000" : "";
    if (!dev && browser) {
        url = location.protocol + "//" + location.host;
    }

    let downhill = 300;
    let uphill = 700;
    let length = 10000;

    let prediction = "n.a.";
    let linearPrediction = "n.a.";
    let din33466 = "n.a.";
    let sac = "n.a.";

    let debounceId;
    let mapContainer;
    let map;
    let drawnPoints = [];
    let polyline;
    let markers = [];
    let mapMode = false; // false = manual input, true = map mode
    let mapInfoMsg = "Klicke auf die Karte um eine Route einzuzeichnen.";

    async function predict() {
        let result = await fetch(
            url + "/api/predict?" + new URLSearchParams({ downhill, uphill, length }),
            { method: "GET" }
        );
        let data = await result.json();
        prediction = data.time;
        linearPrediction = data.linear;
        din33466 = data.din33466;
        sac = data.sac;
    }

    onMount(() => {
        predict();
    });

    function schedulePredict() {
        if (debounceId) clearTimeout(debounceId);
        debounceId = setTimeout(() => predict(), 300);
    }

    // Haversine distance between two [lat, lng] points in meters
    function haversine(a, b) {
        const R = 6371000;
        const toRad = (d) => (d * Math.PI) / 180;
        const dLat = toRad(b[0] - a[0]);
        const dLon = toRad(b[1] - a[1]);
        const s =
            Math.sin(dLat / 2) ** 2 +
            Math.cos(toRad(a[0])) * Math.cos(toRad(b[0])) * Math.sin(dLon / 2) ** 2;
        return R * 2 * Math.atan2(Math.sqrt(s), Math.sqrt(1 - s));
    }

    async function fetchElevation(lat, lng) {
        try {
            const res = await fetch(
                `https://api.open-meteo.com/v1/elevation?latitude=${lat}&longitude=${lng}`
            );
            const data = await res.json();
            return data.elevation?.[0] ?? 0;
        } catch {
            return 0;
        }
    }

    async function initMap() {
        if (!browser) return;
        mapMode = true;

        // Dynamically load Leaflet
        if (!window.L) {
            await new Promise((resolve) => {
                const link = document.createElement("link");
                link.rel = "stylesheet";
                link.href = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css";
                document.head.appendChild(link);
                const script = document.createElement("script");
                script.src = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js";
                script.onload = resolve;
                document.head.appendChild(script);
            });
        }

        await new Promise((r) => setTimeout(r, 100));

        const L = window.L;
        map = L.map(mapContainer).setView([46.8, 8.2], 8);
        L.tileLayer("https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png", {
            attribution: "© OpenTopoMap",
            maxZoom: 17,
        }).addTo(map);

        map.on("click", async (e) => {
            const { lat, lng } = e.latlng;
            drawnPoints = [...drawnPoints, [lat, lng]];

            const marker = L.circleMarker([lat, lng], {
                radius: 6,
                color: "#0d6efd",
                fillColor: "#0d6efd",
                fillOpacity: 0.9,
            }).addTo(map);
            markers = [...markers, marker];

            if (polyline) map.removeLayer(polyline);
            if (drawnPoints.length > 1) {
                polyline = L.polyline(drawnPoints, { color: "#0d6efd", weight: 3 }).addTo(map);
            }

            await recalculateFromMap();
        });
    }

    async function recalculateFromMap() {
        if (drawnPoints.length < 2) {
            mapInfoMsg = `${drawnPoints.length} Punkt gesetzt. Mindestens 2 Punkte nötig.`;
            return;
        }

        mapInfoMsg = "Berechne Route...";

        // Total distance
        let totalDist = 0;
        for (let i = 1; i < drawnPoints.length; i++) {
            totalDist += haversine(drawnPoints[i - 1], drawnPoints[i]);
        }

        // Elevations for all points
        const elevations = await Promise.all(
            drawnPoints.map(([lat, lng]) => fetchElevation(lat, lng))
        );

        let totalUp = 0;
        let totalDown = 0;
        for (let i = 1; i < elevations.length; i++) {
            const diff = elevations[i] - elevations[i - 1];
            if (diff > 0) totalUp += diff;
            else totalDown += Math.abs(diff);
        }

        const maxElev = Math.max(...elevations);

        length = Math.round(totalDist);
        uphill = Math.round(totalUp);
        downhill = Math.round(totalDown);

        mapInfoMsg = `Route: ${(totalDist / 1000).toFixed(1)} km | Aufstieg: ${Math.round(totalUp)} m | Abstieg: ${Math.round(totalDown)} m | Max. Höhe: ${Math.round(maxElev)} m`;

        await predict();
    }

    function resetMap() {
        if (map) {
            markers.forEach((m) => map.removeLayer(m));
            if (polyline) map.removeLayer(polyline);
        }
        drawnPoints = [];
        markers = [];
        polyline = null;
        mapInfoMsg = "Klicke auf die Karte um eine Route einzuzeichnen.";
        downhill = 300;
        uphill = 700;
        length = 10000;
        predict();
    }

    function undoLastPoint() {
        if (drawnPoints.length === 0) return;
        drawnPoints = drawnPoints.slice(0, -1);
        const lastMarker = markers[markers.length - 1];
        if (lastMarker) map.removeLayer(lastMarker);
        markers = markers.slice(0, -1);
        if (polyline) map.removeLayer(polyline);
        if (drawnPoints.length > 1) {
            polyline = window.L.polyline(drawnPoints, { color: "#0d6efd", weight: 3 }).addTo(map);
        } else {
            polyline = null;
        }
        if (drawnPoints.length >= 2) recalculateFromMap();
        else mapInfoMsg = `${drawnPoints.length} Punkt gesetzt. Mindestens 2 Punkte nötig.`;
    }
</script>

<svelte:head>
    <title>HikePlanner</title>
</svelte:head>

<div class="app-bg">
    <main class="container py-5">
        <div class="row g-4 align-items-start">

            <!-- Left: Input Panel -->
            <div class="col-lg-5">
                <div class="p-4 p-lg-5 bg-white shadow-sm rounded-4">
                    <h1 class="display-6 fw-bold mb-2">HikePlanner</h1>
                    <p class="text-muted mb-4">
                        Schätze die Gehzeit basierend auf Distanz und Höhenmetern.
                    </p>

                    <!-- Map toggle button -->
                    {#if !mapMode}
                        <button class="btn btn-outline-success w-100 mb-4" on:click={initMap}>
                            Route auf Karte einzeichnen
                        </button>
                    {:else}
                        <div class="alert alert-info py-2 mb-3" style="font-size:0.85rem">
                            {mapInfoMsg}
                        </div>
                        <div class="d-flex gap-2 mb-3">
                            <button class="btn btn-outline-secondary btn-sm" on:click={undoLastPoint}>
                                Letzten Punkt entfernen
                            </button>
                            <button class="btn btn-outline-danger btn-sm" on:click={resetMap}>
                                Route zurücksetzen
                            </button>
                        </div>
                    {/if}

                    <form class="vstack gap-3" on:submit|preventDefault={predict}>
                        <div>
                            <label class="form-label fw-semibold">Abwärts [m]</label>
                            <div class="row g-2 align-items-center">
                                <div class="col-4">
                                    <input type="number" class="form-control" bind:value={downhill}
                                        min="0" max="10000" on:input={schedulePredict} />
                                </div>
                                <div class="col-8">
                                    <input type="range" class="form-range" bind:value={downhill}
                                        min="0" max="10000" step="10" on:input={schedulePredict} />
                                </div>
                            </div>
                        </div>

                        <div>
                            <label class="form-label fw-semibold">Aufwärts [m]</label>
                            <div class="row g-2 align-items-center">
                                <div class="col-4">
                                    <input type="number" class="form-control" bind:value={uphill}
                                        min="0" max="10000" on:input={schedulePredict} />
                                </div>
                                <div class="col-8">
                                    <input type="range" class="form-range" bind:value={uphill}
                                        min="0" max="10000" step="10" on:input={schedulePredict} />
                                </div>
                            </div>
                        </div>

                        <div>
                            <label class="form-label fw-semibold">Distanz [m]</label>
                            <div class="row g-2 align-items-center">
                                <div class="col-4">
                                    <input type="number" class="form-control" bind:value={length}
                                        min="0" max="100000" on:input={schedulePredict} />
                                </div>
                                <div class="col-8">
                                    <input type="range" class="form-range" bind:value={length}
                                        min="0" max="100000" step="100" on:input={schedulePredict} />
                                </div>
                            </div>
                        </div>

                        <div class="d-grid">
                            <button class="btn btn-primary btn-lg" type="submit">Predict</button>
                        </div>
                    </form>
                </div>
            </div>

            <!-- Right: Map + Results -->
            <div class="col-lg-7">

                <!-- Map -->
                {#if mapMode}
                    <div class="bg-white shadow-sm rounded-4 mb-4 overflow-hidden" style="height: 340px;">
                        <div bind:this={mapContainer} style="height: 100%; width: 100%;"></div>
                    </div>
                {/if}

                <!-- Results -->
                <div class="p-4 p-lg-5 bg-white shadow-sm rounded-4">
                    <h2 class="h5 mb-4 fw-semibold">Geschätzte Dauer</h2>
                    <div class="table-responsive">
                        <table class="table table-sm align-middle">
                            <tbody>
                                <tr>
                                    <th scope="row" class="text-muted">Model (Gradient Boosting Regressor)</th>
                                    <td class="fw-semibold text-primary">{prediction}</td>
                                </tr>
                                <tr>
                                    <th scope="row" class="text-muted">Model (Linear Regression)</th>
                                    <td class="fw-semibold">{linearPrediction}</td>
                                </tr>
                                <tr>
                                    <th scope="row" class="text-muted">DIN33466</th>
                                    <td class="fw-semibold">{din33466}</td>
                                </tr>
                                <tr>
                                    <th scope="row" class="text-muted">SAC</th>
                                    <td class="fw-semibold">{sac}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    <!-- Visual bar chart -->
                    {#if prediction !== "n.a."}
                        {@const toMin = (t) => {
                            const parts = t.split(":");
                            return parseInt(parts[0]) * 60 + parseInt(parts[1]);
                        }}
                        {@const vals = [
                            { label: "GBR", val: toMin(prediction), color: "#0d6efd" },
                            { label: "Linear", val: toMin(linearPrediction), color: "#6c757d" },
                            { label: "DIN33466", val: toMin(din33466), color: "#fd7e14" },
                            { label: "SAC", val: toMin(sac), color: "#198754" },
                        ]}
                        {@const maxVal = Math.max(...vals.map((v) => v.val))}
                        <div class="mt-4">
                            <p class="text-muted small mb-2">Vergleich (Minuten)</p>
                            {#each vals as item}
                                <div class="d-flex align-items-center mb-2 gap-2">
                                    <div style="width: 70px; font-size: 0.8rem; text-align: right; color: #6c757d">{item.label}</div>
                                    <div class="flex-grow-1 bg-light rounded" style="height: 22px; overflow: hidden;">
                                        <div
                                            style="width: {(item.val / maxVal) * 100}%; height: 100%; background: {item.color}; border-radius: 4px; transition: width 0.4s ease;"
                                        ></div>
                                    </div>
                                    <div style="width: 55px; font-size: 0.8rem; font-weight: 600; color: {item.color}">{item.val} min</div>
                                </div>
                            {/each}
                        </div>
                    {/if}
                </div>
            </div>

        </div>
    </main>
</div>