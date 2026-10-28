let crowdChart = null;
let threatChart = null;

document.addEventListener("DOMContentLoaded", function () {
    initCharts();
    loadDashboardSummary();

    const refreshBtn = document.getElementById("btn-refresh-dashboard");
    if (refreshBtn) {
        refreshBtn.addEventListener("click", function () {
            loadDashboardSummary();
        });
    }

    // Auto-refresh telemetry every 10 seconds
    setInterval(loadDashboardSummary, 10000);
});

function initCharts() {
    const crowdCtx = document.getElementById("crowdFlowChart");
    if (crowdCtx) {
        crowdChart = new Chart(crowdCtx, {
            type: "line",
            data: {
                labels: ["16:00", "17:00", "18:00", "19:00", "20:00", "21:00", "22:00", "23:00"],
                datasets: [{
                    label: "Live People Count",
                    data: [24, 38, 55, 78, 110, 142, 126, 107],
                    borderColor: "#06b6d4",
                    backgroundColor: "rgba(6, 182, 212, 0.15)",
                    borderWidth: 2,
                    tension: 0.35,
                    fill: true,
                    pointBackgroundColor: "#06b6d4"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: "#1f293d" },
                        ticks: { color: "#9ca3af" }
                    },
                    x: {
                        grid: { color: "rgba(255,255,255,0.02)" },
                        ticks: { color: "#9ca3af" }
                    }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    const threatCtx = document.getElementById("threatPieChart");
    if (threatCtx) {
        threatChart = new Chart(threatCtx, {
            type: "doughnut",
            data: {
                labels: ["Weapon Flags", "Zone Intrusion", "Loitering", "Running/Sudden"],
                datasets: [{
                    data: [1, 1, 3, 2],
                    backgroundColor: [
                        "#ef4444",
                        "#f97316",
                        "#f59e0b",
                        "#3b82f6"
                    ],
                    borderColor: "#111827",
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: "right",
                        labels: { color: "#9ca3af", boxWidth: 12, font: { size: 10 } }
                    }
                },
                cutout: "65%"
            }
        });
    }
}

async function loadDashboardSummary() {
    try {
        const response = await fetch("/api/dashboard/summary");
        if (!response.ok) return;
        const data = await response.json();

        // Update KPI values
        const countEl = document.getElementById("kpi-people-count");
        if (countEl) countEl.innerText = data.total_people_detected;

        const threatsEl = document.getElementById("kpi-threats-count");
        if (threatsEl) threatsEl.innerText = data.active_threats_count;

        const riskEl = document.getElementById("kpi-risk-score");
        if (riskEl) riskEl.innerText = data.highest_risk_score;

        // Update Charts if initialized
        if (crowdChart && data.hourly_people_flow) {
            crowdChart.data.labels = data.hourly_timestamps;
            crowdChart.data.datasets[0].data = data.hourly_people_flow;
            crowdChart.update();
        }
    } catch (err) {
        console.error("Dashboard summary polling error:", err);
    }
}

async function ackAlert(eventId) {
    try {
        const response = await fetch(`/api/alerts/${eventId}/ack`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ officer_name: "Duty Supervisor" })
        });
        const res = await response.json();
        if (res.status === "success") {
            const badge = document.getElementById(`status-badge-${eventId}`);
            if (badge) {
                badge.className = "badge bg-warning text-dark";
                badge.innerText = "ACKNOWLEDGED";
            }
        }
    } catch (err) {
        alert("Failed to acknowledge alert: " + err);
    }
}

async function resolveAlert(eventId) {
    try {
        const response = await fetch(`/api/alerts/${eventId}/resolve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const res = await response.json();
        if (res.status === "success") {
            const badge = document.getElementById(`status-badge-${eventId}`);
            if (badge) {
                badge.className = "badge bg-success";
                badge.innerText = "RESOLVED";
            }
        }
    } catch (err) {
        alert("Failed to resolve alert: " + err);
    }
}
