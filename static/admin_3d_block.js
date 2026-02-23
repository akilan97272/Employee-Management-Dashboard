// admin_3d_block.js
function notify(message, tone = "neutral") {
    if (window.showToast) {
        window.showToast(String(message || ""), tone);
        return;
    }
    alert(String(message || ""));
}

async function searchEmployee() {
    const input = document.getElementById("employeeSearch");
    const name = (input?.value || "").trim();
    if (!name) {
        notify("Enter employee name", "warning");
        return;
    }
    try {
        const res = await fetch(`/admin/3d-block/search?employee_name=${encodeURIComponent(name)}`, {
            method: "GET",
            headers: { Accept: "application/json" },
            cache: "no-store",
        });
        let data = {};
        try {
            data = await res.json();
        } catch (_) {
            const text = await res.text().catch(() => "");
            data = { detail: text || "" };
        }
        if (!res.ok) {
            let detail = String(data?.detail || "").trim();
            if (!detail && res.status === 401) detail = "Session expired. Please login again.";
            if (!detail && res.status === 403) detail = "Access denied for employee search.";
            if (!detail) detail = "Search failed";
            notify(String(detail), "error");
            return;
        }

        if (data?.status === "error") {
            notify(data?.message || "Employee search is temporarily unavailable. Please try again.", "warning");
            return;
        }

        if (data?.status === "found" && window.Admin3DScene && typeof window.Admin3DScene.focusBuildingByIds === "function") {
            const ok = window.Admin3DScene.focusBuildingByIds(data.area_id, data.building_id, data.employee || null);
            if (ok) {
                notify(
                    `${data.employee?.name || "Employee"} found in ${data.building_name || "building"}`,
                    "success",
                );
                return;
            }
        }
        notify(data?.message || "Employee not found or currently not inside any building.", "warning");
    } catch (_) {
        notify("Search failed", "error");
    }
}

function filterArea() {
    const select = document.getElementById("areaFilter");
    const areaId = (select?.value || "").trim() || null;
    if (window.Admin3DScene && typeof window.Admin3DScene.focusArea === "function") {
        window.Admin3DScene.focusArea(areaId);
    }
}

function openSettingsPage() {
    window.location.href = "/admin/3d-block/settings";
}

document.addEventListener("DOMContentLoaded", () => {
    const input = document.getElementById("employeeSearch");
    const datalist = document.getElementById("employeeSearchSuggestions");
    if (!input) return;
    let suggestionTimer = null;

    async function loadSuggestions() {
        if (!datalist) return;
        const q = (input.value || "").trim();
        if (!q) {
            datalist.innerHTML = "";
            return;
        }
        try {
            const res = await fetch(`/admin/3d-block/search-suggestions?q=${encodeURIComponent(q)}&limit=12`, {
                method: "GET",
                headers: { Accept: "application/json" },
                cache: "no-store",
            });
            if (!res.ok) {
                datalist.innerHTML = "";
                return;
            }
            const data = await res.json().catch(() => ({}));
            const items = Array.isArray(data?.items) ? data.items : [];
            datalist.innerHTML = "";
            items.forEach((item) => {
                const option = document.createElement("option");
                option.value = String(item?.name || "");
                option.label = String(item?.label || option.value);
                datalist.appendChild(option);
            });
        } catch (_) {
            datalist.innerHTML = "";
        }
    }

    input.addEventListener("input", () => {
        if (suggestionTimer) {
            clearTimeout(suggestionTimer);
            suggestionTimer = null;
        }
        suggestionTimer = setTimeout(loadSuggestions, 180);
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            searchEmployee();
        }
    });
});
