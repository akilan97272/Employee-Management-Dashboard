// admin_3d_block_controls.js

function createBasicPanZoomControls(camera, renderer) {
    const dom = renderer && renderer.domElement ? renderer.domElement : null;
    const target = (typeof THREE !== "undefined" && THREE.Vector3)
        ? new THREE.Vector3(0, 0, 0)
        : { x: 0, y: 0, z: 0 };
    let dragging = false;
    let lastX = 0;
    let lastY = 0;
    const minDistance = 80;
    const maxDistance = 900;

    function clampDistance() {
        if (typeof THREE === "undefined" || !THREE.Vector3) return;
        const offset = camera.position.clone().sub(target);
        const dist = offset.length();
        if (dist < minDistance) {
            offset.setLength(minDistance);
            camera.position.copy(target).add(offset);
        } else if (dist > maxDistance) {
            offset.setLength(maxDistance);
            camera.position.copy(target).add(offset);
        }
    }

    function onPointerDown(e) {
        dragging = true;
        lastX = e.clientX;
        lastY = e.clientY;
    }

    function onPointerMove(e) {
        if (!dragging || typeof THREE === "undefined" || !THREE.Vector3) return;
        const dx = e.clientX - lastX;
        const dy = e.clientY - lastY;
        lastX = e.clientX;
        lastY = e.clientY;
        const panScale = Math.max(0.25, camera.position.distanceTo(target) * 0.0016);
        const move = new THREE.Vector3(-dx * panScale, 0, -dy * panScale);
        camera.position.add(move);
        target.add(move);
    }

    function onPointerUp() {
        dragging = false;
    }

    function onWheel(e) {
        if (typeof THREE === "undefined" || !THREE.Vector3) return;
        e.preventDefault();
        const dir = camera.position.clone().sub(target).normalize();
        const dist = camera.position.distanceTo(target);
        const zoomFactor = e.deltaY > 0 ? 1.08 : 0.92;
        const nextDist = Math.min(maxDistance, Math.max(minDistance, dist * zoomFactor));
        camera.position.copy(target).add(dir.multiplyScalar(nextDist));
    }

    if (dom) {
        dom.addEventListener("pointerdown", onPointerDown);
        window.addEventListener("pointermove", onPointerMove);
        window.addEventListener("pointerup", onPointerUp);
        dom.addEventListener("wheel", onWheel, { passive: false });
    }

    return {
        target,
        update: function () {
            clampDistance();
            if (camera && camera.lookAt && typeof THREE !== "undefined" && THREE.Vector3) {
                camera.lookAt(target);
            }
        },
        dispose: function () {
            if (!dom) return;
            dom.removeEventListener("pointerdown", onPointerDown);
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", onPointerUp);
            dom.removeEventListener("wheel", onWheel);
        },
    };
}

function enableOrbitControls(camera, renderer) {
    if (typeof THREE === "undefined") {
        return {
            target: { x: 0, y: 0, z: 0, copy: function () { return this; }, clone: function () { return this; } },
            update: function () {},
        };
    }
    if (typeof THREE.MapControls !== "function" && typeof THREE.OrbitControls !== "function") {
        return createBasicPanZoomControls(camera, renderer);
    }

    const ControlCtor = typeof THREE.OrbitControls === "function" ? THREE.OrbitControls : THREE.MapControls;
    const controls = new ControlCtor(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.enablePan = true;
    controls.enableRotate = true;
    controls.panSpeed = 1.05;
    controls.zoomSpeed = 1.15;
    controls.rotateSpeed = 0.9;
    controls.enableKeys = true;
    controls.keyPanSpeed = 20;
    controls.minPolarAngle = 0.05;
    controls.maxPolarAngle = 1.52;
    controls.minDistance = 120;
    controls.maxDistance = 460;
    controls.minAzimuthAngle = -Infinity;
    controls.maxAzimuthAngle = Infinity;
    controls.mouseButtons = {
        LEFT: THREE.MOUSE.ROTATE,
        MIDDLE: THREE.MOUSE.DOLLY,
        RIGHT: THREE.MOUSE.PAN,
    };
    controls.touches = {
        ONE: THREE.TOUCH.ROTATE,
        TWO: THREE.TOUCH.DOLLY_PAN,
    };
    if (renderer && renderer.domElement) {
        renderer.domElement.addEventListener("contextmenu", (e) => e.preventDefault());
    }
    if (typeof controls.listenToKeyEvents === "function") {
        controls.listenToKeyEvents(window);
    }
    controls.target.set(0, 0, 0);
    controls.update();
    return controls;
}

function checkerTexture(size = 1024, cell = 32, cA = "#120311", cB = "#2a0626") {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    for (let y = 0; y < size; y += cell) {
        for (let x = 0; x < size; x += cell) {
            const odd = ((x / cell) + (y / cell)) % 2;
            ctx.fillStyle = odd ? cA : cB;
            ctx.fillRect(x, y, cell, cell);
        }
    }
    const t = new THREE.CanvasTexture(canvas);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(10, 10);
    return t;
}

function asphaltTexture(size = 1024) {
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#8f949e";
    ctx.fillRect(0, 0, size, size);

    for (let i = 0; i < 16000; i += 1) {
        const x = Math.random() * size;
        const y = Math.random() * size;
        const a = Math.random() * 0.08;
        ctx.fillStyle = `rgba(255,255,255,${a.toFixed(3)})`;
        ctx.fillRect(x, y, 1, 1);
    }

    const t = new THREE.CanvasTexture(canvas);
    t.wrapS = THREE.RepeatWrapping;
    t.wrapT = THREE.RepeatWrapping;
    t.repeat.set(4, 4);
    return t;
}

function roadMaterial() {
    return new THREE.MeshStandardMaterial({
        map: asphaltTexture(),
        roughness: 0.95,
        metalness: 0.03,
    });
}

function addRoadLines(scene, x, z, w, h, vertical) {
    const lineMat = new THREE.MeshStandardMaterial({ color: 0xf8fafc });
    const centerLineMat = new THREE.MeshStandardMaterial({ color: 0xf4b840 });

    const laneCount = 26;
    for (let i = -laneCount; i <= laneCount; i += 2) {
        const dash = new THREE.Mesh(
            new THREE.PlaneGeometry(0.35, 5),
            lineMat
        );
        dash.rotation.x = -Math.PI / 2;
        if (vertical) {
            dash.position.set(x, 0.08, i * 6 + z);
        } else {
            dash.position.set(i * 6 + x, 0.08, z);
            dash.rotation.z = Math.PI / 2;
        }
        scene.add(dash);
    }

    const center = new THREE.Mesh(
        new THREE.PlaneGeometry(vertical ? 0.45 : Math.min(w * 0.85, 420), vertical ? Math.min(h * 0.85, 420) : 0.45),
        centerLineMat
    );
    center.rotation.x = -Math.PI / 2;
    center.position.set(x, 0.085, z);
    scene.add(center);
}

function addStreetLights(scene, fromX, toX, z, step, vertical = false) {
    for (let p = fromX; p <= toX; p += step) {
        const pole = new THREE.Mesh(
            new THREE.CylinderGeometry(0.12, 0.12, 5.8, 10),
            new THREE.MeshStandardMaterial({ color: 0xbfd4f0, roughness: 0.45, metalness: 0.4 })
        );
        if (!vertical) pole.position.set(p, 2.9, z);
        else pole.position.set(z, 2.9, p);
        scene.add(pole);
    }
}

function addSceneDetails(scene) {
    // background plane with checker
    const bg = new THREE.Mesh(
        new THREE.PlaneGeometry(1600, 1600),
        new THREE.MeshStandardMaterial({
            map: checkerTexture(),
            roughness: 1.0,
            metalness: 0.0,
            side: THREE.DoubleSide,
        })
    );
    bg.rotation.x = -Math.PI / 2;
    bg.position.y = -0.02;
    scene.add(bg);

    // main central plot
    const plot = new THREE.Mesh(
        new THREE.PlaneGeometry(420, 320),
        roadMaterial()
    );
    plot.rotation.x = -Math.PI / 2;
    plot.position.y = 0.02;
    scene.add(plot);

    // roads similar to reference: cross + perimeter bands
    const roads = [
        { x: 0, z: -170, w: 980, h: 58, vertical: false },
        { x: 230, z: 0, w: 58, h: 860, vertical: true },
        { x: -230, z: 0, w: 58, h: 860, vertical: true },
        { x: 0, z: 170, w: 980, h: 58, vertical: false },
        { x: 0, z: 0, w: 920, h: 52, vertical: false },
    ];
    roads.forEach((r) => {
        const road = new THREE.Mesh(new THREE.PlaneGeometry(r.w, r.h), roadMaterial());
        road.rotation.x = -Math.PI / 2;
        road.position.set(r.x, 0.03, r.z);
        scene.add(road);
        addRoadLines(scene, r.x, r.z, r.w, r.h, r.vertical);
    });

    addStreetLights(scene, -440, 440, -200, 26, false);
    addStreetLights(scene, -440, 440, 200, 26, false);
    addStreetLights(scene, -390, 390, -260, 26, true);
    addStreetLights(scene, -390, 390, 260, 26, true);

    const hemi = new THREE.HemisphereLight(0xffffff, 0x331333, 0.82);
    scene.add(hemi);
    const dirA = new THREE.DirectionalLight(0xffffff, 0.72);
    dirA.position.set(160, 260, 120);
    scene.add(dirA);
    const dirB = new THREE.DirectionalLight(0xb3d4ff, 0.24);
    dirB.position.set(-180, 140, -120);
    scene.add(dirB);
}

function highlightBuilding(buildingObj, highlight = true, options = {}) {
    if (!buildingObj) return;
    const mode = String(options?.mode || "click").toLowerCase();
    const highlightColor = mode === "employee" ? 0xf59e0b : 0x3ed2ff; // employee=orange, click=cyan
    const highlightIntensity = mode === "employee" ? 0.42 : 0.35;
    buildingObj.traverse((child) => {
        if (!child.isMesh || !child.material) return;
        const materials = Array.isArray(child.material) ? child.material : [child.material];
        materials.forEach((mat, idx) => {
            if (!mat || !("emissive" in mat)) return;
            if (!child.userData.__hlState) child.userData.__hlState = {};
            const key = String(idx);

            if (highlight) {
                // Preserve original material only once, otherwise repeated hover overwrites original with highlighted blue.
                if (!child.userData.__hlState[key]) {
                    child.userData.__hlState[key] = {
                        emissive: mat.emissive ? mat.emissive.clone() : new THREE.Color(0x000000),
                        intensity: Number.isFinite(mat.emissiveIntensity) ? mat.emissiveIntensity : 0,
                    };
                }
                mat.emissive = new THREE.Color(highlightColor);
                mat.emissiveIntensity = highlightIntensity;
            } else if (child.userData.__hlState[key]) {
                const old = child.userData.__hlState[key];
                mat.emissive = old.emissive.clone();
                mat.emissiveIntensity = old.intensity;
                delete child.userData.__hlState[key];
            }
            mat.needsUpdate = true;
        });
        if (!highlight && child.userData.__hlState && Object.keys(child.userData.__hlState).length === 0) {
            delete child.userData.__hlState;
        }
    });
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function initialsFromName(name) {
    const parts = String(name || "").trim().split(/\s+/).filter(Boolean);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 1).toUpperCase();
    return (parts[0].slice(0, 1) + parts[parts.length - 1].slice(0, 1)).toUpperCase();
}

function floorBadgeHtml(rawFloor) {
    const label = String(rawFloor || "Unknown").trim() || "Unknown";
    const low = label.toLowerCase();
    let bg = "rgba(71,85,105,.35)";
    let border = "rgba(148,163,184,.45)";
    let fg = "#cbd5e1";

    if (low.includes("ground")) {
        bg = "rgba(6,95,70,.35)";
        border = "rgba(16,185,129,.45)";
        fg = "#a7f3d0";
    } else if (low.includes("basement")) {
        bg = "rgba(91,33,182,.35)";
        border = "rgba(167,139,250,.45)";
        fg = "#ddd6fe";
    } else {
        const m = low.match(/(\d+)/);
        if (m) {
            const n = Number(m[1]);
            if (Number.isFinite(n)) {
                const hue = (n * 37) % 360;
                bg = `hsla(${hue}, 78%, 42%, .35)`;
                border = `hsla(${hue}, 86%, 64%, .50)`;
                fg = `hsl(${hue}, 95%, 86%)`;
            }
        }
    }

    return `<span style="display:inline-flex;align-items:center;border:1px solid ${border};background:${bg};color:${fg};border-radius:999px;padding:2px 8px;font-size:10px;font-weight:800;line-height:1.3;letter-spacing:.02em;">${escapeHtml(label)}</span>`;
}

function floorBadgesHtml(rawFloors) {
    const labels = String(rawFloors || "")
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
    if (!labels.length) return floorBadgeHtml("Unknown");
    return labels.map((label) => floorBadgeHtml(label)).join(" ");
}

function positionBuildingSidebars() {
    const host = document.getElementById("block-visualization")?.parentElement || document.body;
    const infoPanel = document.getElementById("building-info-sidebar");
    const peoplePanel = document.getElementById("building-people-sidebar");
    if (!host || (!infoPanel && !peoplePanel)) return;

    const pad = 16;
    const gap = 12;
    const top = 72; // keep clear of live status controls row
    const hostWidth = Math.max(320, host.clientWidth || window.innerWidth || 320);
    const maxPanelWidth = Math.max(240, hostWidth - (pad * 2));

    if (infoPanel) {
        const infoWidth = Math.min(300, maxPanelWidth);
        infoPanel.style.width = `${infoWidth}px`;
        infoPanel.style.left = `${pad}px`;
        infoPanel.style.top = `${top}px`;
    }

    if (peoplePanel) {
        const peopleWidth = Math.min(340, maxPanelWidth);
        peoplePanel.style.width = `${peopleWidth}px`;
        const infoWidth = infoPanel ? Math.min(300, maxPanelWidth) : 0;
        const sideBySideFits = !!infoPanel && (pad + infoWidth + gap + peopleWidth + pad) <= hostWidth;
        if (sideBySideFits) {
            peoplePanel.style.left = `${pad + infoWidth + gap}px`;
            peoplePanel.style.top = `${top}px`;
        } else {
            const infoHeight = infoPanel ? Math.max(180, infoPanel.offsetHeight || 0) : 0;
            const stackedTop = infoPanel ? (top + infoHeight + gap) : top;
            peoplePanel.style.left = `${pad}px`;
            peoplePanel.style.top = `${stackedTop}px`;
        }
    }
}

function ensureBuildingPeoplePanel() {
    let panel = document.getElementById("building-people-sidebar");
    if (panel) return panel;
    panel = document.createElement("div");
    panel.id = "building-people-sidebar";
    panel.style.position = "absolute";
    panel.style.top = "16px";
    panel.style.left = "330px";
    panel.style.width = "340px";
    panel.style.maxHeight = "70vh";
    panel.style.overflow = "hidden";
    panel.style.zIndex = "1211";
    panel.style.background = "rgba(15, 23, 42, 0.96)";
    panel.style.color = "#e2e8f0";
    panel.style.border = "1px solid rgba(148, 163, 184, .35)";
    panel.style.borderRadius = "10px";
    panel.style.fontSize = "12px";
    panel.style.fontWeight = "700";
    panel.style.backdropFilter = "blur(4px)";
    panel.style.boxShadow = "0 12px 24px rgba(2, 6, 23, 0.35)";
    panel.style.display = "none";

    const host = document.getElementById("block-visualization")?.parentElement || document.body;
    if (host && !host.style.position) host.style.position = "relative";
    host.appendChild(panel);
    if (!window.__buildingSidebarResizeBound) {
        window.__buildingSidebarResizeBound = true;
        window.addEventListener("resize", () => positionBuildingSidebars());
    }
    positionBuildingSidebars();
    return panel;
}

function hideBuildingPeoplePanel() {
    const panel = document.getElementById("building-people-sidebar");
    if (panel) panel.style.display = "none";
}

function renderBuildingPeoplePanel(payload, loading = false, error = "") {
    const panel = ensureBuildingPeoplePanel();
    const people = Array.isArray(payload?.people) ? payload.people : [];
    const title = `${payload?.building_name || payload?.buildingName || "Building"} - People`;
    const subtitle = `Area: ${payload?.area_name || payload?.areaName || "-"}`;
    const floorLabel = String(payload?.floor_label || payload?.floor || "Unknown");
    const listHtml = loading
        ? `<div style="padding:16px 14px;color:#cbd5e1;opacity:.9;">Loading people...</div>`
        : error
            ? `<div style="padding:16px 14px;color:#fecaca;background:rgba(127,29,29,.25);">${escapeHtml(error)}</div>`
            : people.length
                ? people.map((person) => {
                    const photoUrl = String(person?.photo_url || "").trim();
                    const name = escapeHtml(person?.name || "-");
                    const employeeId = escapeHtml(person?.employee_id || "-");
                    const initials = escapeHtml(initialsFromName(person?.name || ""));
                    const inTime = escapeHtml(person?.in_time || "-");
                    const floorBadge = floorBadgeHtml(person?.floor || floorLabel);
                    const avatar = photoUrl
                        ? `<img src="${escapeHtml(photoUrl)}" alt="${name}" style="width:40px;height:40px;border-radius:999px;object-fit:cover;border:1px solid rgba(148,163,184,.35);" onerror="this.style.display='none'; this.nextElementSibling.style.display='grid';"><div style="display:none;width:40px;height:40px;border-radius:999px;place-items:center;background:rgba(30,64,175,.4);color:#bfdbfe;border:1px solid rgba(96,165,250,.35);font-size:12px;font-weight:800;">${initials}</div>`
                        : `<div style="width:40px;height:40px;border-radius:999px;display:grid;place-items:center;background:rgba(30,64,175,.4);color:#bfdbfe;border:1px solid rgba(96,165,250,.35);font-size:12px;font-weight:800;">${initials}</div>`;
                    return `
                      <div style="display:flex;align-items:center;gap:10px;padding:10px 12px;border-bottom:1px solid rgba(148,163,184,.16);">
                        ${avatar}
                        <div style="min-width:0;flex:1;">
                          <div style="font-size:12px;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${name}</div>
                          <div style="font-size:10px;color:#93c5fd;letter-spacing:.02em;margin-top:2px;">${employeeId}</div>
                          <div style="font-size:10px;color:#94a3b8;margin-top:3px;">${floorBadge}</div>
                          <div style="font-size:10px;color:#94a3b8;margin-top:2px;">In: ${inTime}</div>
                        </div>
                      </div>
                    `;
                }).join("")
                : `<div style="padding:16px 14px;color:#cbd5e1;opacity:.9;">No people currently inside this building.</div>`;

    panel.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;padding:10px 12px;border-bottom:1px solid rgba(148,163,184,.22);">
        <div style="min-width:0;">
          <div style="font-size:13px;color:#f8fafc;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(title)}</div>
          <div style="margin-top:2px;font-size:10px;color:#94a3b8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(subtitle)} | ${floorBadgesHtml(floorLabel)}</div>
        </div>
        <button type="button" id="buildingPeopleCloseBtn" style="border:1px solid rgba(148,163,184,.35);background:transparent;color:#cbd5e1;border-radius:6px;padding:2px 8px;cursor:pointer;">Close</button>
      </div>
      <div style="max-height:calc(70vh - 56px);overflow-y:auto;">
        ${listHtml}
      </div>
    `;
    const closeBtn = panel.querySelector("#buildingPeopleCloseBtn");
    if (closeBtn) {
        closeBtn.addEventListener("click", () => hideBuildingPeoplePanel());
    }
    panel.style.display = "block";
    positionBuildingSidebars();
}

async function openBuildingPeoplePanel(payload) {
    const areaId = payload?.areaId ?? payload?.area_id;
    const buildingId = payload?.buildingId ?? payload?.building_id;
    if (areaId === undefined || areaId === null || buildingId === undefined || buildingId === null) {
        renderBuildingPeoplePanel(payload, false, "Missing building context");
        return;
    }

    renderBuildingPeoplePanel(payload, true);
    try {
        const qs = new URLSearchParams({
            area_id: String(areaId),
            building_id: String(buildingId),
        });
        const res = await fetch(`/admin/3d-block/building-people?${qs.toString()}`, {
            method: "GET",
            headers: { Accept: "application/json" },
            cache: "no-store",
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            const detail = String(data?.detail || "").trim() || "Unable to load people list";
            renderBuildingPeoplePanel(payload, false, detail);
            return;
        }
        renderBuildingPeoplePanel(data, false, "");
    } catch (_) {
        renderBuildingPeoplePanel(payload, false, "Unable to load people list");
    }
}

function showBuildingInfo(buildingObj, info) {
    const payload = info || {};
    const currentPeople = Math.max(0, Number(payload.currentPeople ?? payload.current_people) || 0);
    const requestedMax = Number(payload.maxPeople ?? payload.max_limit_people);
    const maxPeople = Math.max(currentPeople, Number.isFinite(requestedMax) && requestedMax > 0 ? requestedMax : 20);
    const utilization = Math.max(0, Math.min(100, Math.round((currentPeople / Math.max(1, maxPeople)) * 100)));
    const areaSqMValue = Number(payload.footprintAreaSqM ?? payload.areaSqM ?? payload.area_sqm);
    const areaLabel = Number.isFinite(areaSqMValue) && areaSqMValue > 0
        ? `${Math.round(areaSqMValue)} sq m`
        : "Not available";
    const floorLabel = String(payload.floor_label || payload.floor || payload.employee?.floor || "Unknown");

    let panel = document.getElementById("building-info-sidebar");
    if (!panel) {
        panel = document.createElement("div");
        panel.id = "building-info-sidebar";
        panel.style.position = "absolute";
        panel.style.top = "16px";
        panel.style.left = "16px";
        panel.style.width = "300px";
        panel.style.zIndex = "1210";
        panel.style.background = "rgba(15, 23, 42, 0.96)";
        panel.style.color = "#e2e8f0";
        panel.style.padding = "12px";
        panel.style.border = "1px solid rgba(148, 163, 184, .35)";
        panel.style.borderRadius = "10px";
        panel.style.fontSize = "12px";
        panel.style.fontWeight = "700";
        panel.style.backdropFilter = "blur(4px)";
        panel.style.boxShadow = "0 12px 24px rgba(2, 6, 23, 0.35)";
        panel.style.display = "none";

        const host = document.getElementById("block-visualization")?.parentElement || document.body;
        if (host && !host.style.position) host.style.position = "relative";
        host.appendChild(panel);
    }
    if (!window.__buildingSidebarResizeBound) {
        window.__buildingSidebarResizeBound = true;
        window.addEventListener("resize", () => positionBuildingSidebars());
    }

    const meterColor = utilization >= 90
        ? "#ef4444"
        : utilization >= 75
            ? "#f59e0b"
            : "#22d3ee";
    const trendValuesRaw = Array.isArray(payload.trendValues) && payload.trendValues.length
        ? payload.trendValues
        : [Math.max(0, Math.round(currentPeople * 0.6)), Math.max(0, Math.round(currentPeople * 0.75)), Math.max(0, Math.round(currentPeople * 0.9)), currentPeople];
    const trendValues = trendValuesRaw.map((v) => Math.min(maxPeople, Math.max(0, Math.round(Number(v) || 0))));
    const trendLabelsRaw = Array.isArray(payload.trendLabels) && payload.trendLabels.length
        ? payload.trendLabels
        : ["D1", "D2", "D3", "D4"];
    const trendBars = trendValues.map((v, idx) => {
        const h = Math.max(8, Math.round((v / Math.max(1, maxPeople)) * 44));
        const label = String(trendLabelsRaw[idx] || "").slice(0, 3);
        return `<div style="display:flex;flex-direction:column;align-items:center;gap:4px;">
          <div style="width:14px;height:${h}px;background:rgba(34,211,238,.8);border:1px solid rgba(125,211,252,.55);border-radius:4px 4px 2px 2px;"></div>
          <div style="font-size:9px;line-height:1;color:#94a3b8;">${label}</div>
        </div>`;
    }).join("");
    const employee = payload.employee && typeof payload.employee === "object" ? payload.employee : null;
    const employeeDetailHtml = employee ? `
      <div style="margin-top:12px;border-top:1px solid rgba(148,163,184,.22);padding-top:10px;">
        <div style="font-size:10px;opacity:.84;margin-bottom:6px;">Employee Details</div>
        <div style="display:grid;grid-template-columns:1fr auto;gap:6px 8px;font-size:11px;">
          <div style="opacity:.78;">Name</div><div>${employee.name || "-"}</div>
          <div style="opacity:.78;">Employee ID</div><div>${employee.employee_id || "-"}</div>
          <div style="opacity:.78;">Floor</div><div>${floorBadgeHtml(employee.floor || floorLabel)}</div>
          <div style="opacity:.78;">In Time</div><div>${employee.in_time || "-"}</div>
          <div style="opacity:.78;">Out Time</div><div>${employee.out_time || "-"}</div>
          <div style="opacity:.78;">Duration</div><div>${employee.duration ?? "-"}</div>
        </div>
      </div>
    ` : "";

    panel.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;">
        <div style="font-size:13px;color:#f8fafc;letter-spacing:.02em;">${payload.name || "Building"}</div>
        <button type="button" id="buildingInfoCloseBtn" style="border:1px solid rgba(148,163,184,.35);background:transparent;color:#cbd5e1;border-radius:6px;padding:2px 8px;cursor:pointer;">Close</button>
      </div>
      <div style="margin-top:8px;opacity:.86;font-size:11px;">Area: ${payload.areaName || "-"}</div>
      <div style="margin-top:10px;display:grid;grid-template-columns:1fr auto;gap:6px 8px;font-size:11px;">
        <div style="opacity:.78;">Building Area</div><div>${areaLabel}</div>
        <div style="opacity:.78;">Floors Occupied</div><div>${floorBadgesHtml(floorLabel)}</div>
        <div style="opacity:.78;">People Inside</div><button type="button" id="buildingPeopleCountBtn" style="justify-self:end;border:1px solid rgba(59,130,246,.35);background:rgba(30,64,175,.25);color:#bfdbfe;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800;cursor:pointer;">${currentPeople}</button>
        <div style="opacity:.78;">Max Limit</div><div>${maxPeople}</div>
      </div>
      <div style="margin-top:12px;">
        <div style="display:flex;align-items:center;justify-content:space-between;font-size:10px;opacity:.84;">
          <span>Occupancy Meter</span>
          <span>${utilization}%</span>
        </div>
        <div style="margin-top:6px;height:10px;background:rgba(148,163,184,.2);border-radius:999px;overflow:hidden;">
          <div style="height:100%;width:${utilization}%;background:${meterColor};transition:width .25s ease;"></div>
        </div>
      </div>
      <div style="margin-top:12px;">
        <div style="font-size:10px;opacity:.84;">Occupancy Trend (recent)</div>
        <div style="margin-top:6px;height:54px;display:flex;align-items:flex-end;gap:6px;padding:4px 6px;background:rgba(15,23,42,.45);border:1px solid rgba(148,163,184,.28);border-radius:8px;">
          ${trendBars}
        </div>
      </div>
      ${employeeDetailHtml}
    `;

    const closeBtn = panel.querySelector("#buildingInfoCloseBtn");
    if (closeBtn) {
        closeBtn.addEventListener("click", () => hideBuildingInfo());
    }
    const peopleBtn = panel.querySelector("#buildingPeopleCountBtn");
    if (peopleBtn) {
        peopleBtn.addEventListener("click", () => openBuildingPeoplePanel(payload));
    }
    panel.style.display = "block";
    positionBuildingSidebars();
}

function hideBuildingInfo() {
    const panel = document.getElementById("building-info-sidebar");
    if (panel) panel.style.display = "none";
    hideBuildingPeoplePanel();
}

window.Admin3DBlockControls = {
    enableOrbitControls,
    addSceneDetails,
    highlightBuilding,
    showBuildingInfo,
    hideBuildingInfo,
};
