document.addEventListener("DOMContentLoaded", async function () {
    try {
        const response = await fetch("/api/analytics");
        if (!response.ok) return;
        const res = await response.json();

        // 1. Timeline Chart
        const timelineCtx = document.getElementById("timelineChart");
        if (timelineCtx) {
            new Chart(timelineCtx, {
                type: "line",
                data: {
                    labels: res.timeline_data.labels,
                    datasets: [
                        {
                            label: "Footfall Count",
                            data: res.timeline_data.people_count,
                            borderColor: "#3b82f6",
                            backgroundColor: "rgba(59, 130, 246, 0.15)",
                            tension: 0.3,
                            fill: true
                        },
                        {
                            label: "Threat Incidents",
                            data: res.timeline_data.threat_events,
                            borderColor: "#ef4444",
                            backgroundColor: "rgba(239, 68, 68, 0.2)",
                            tension: 0.3,
                            fill: true
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { grid: { color: "#1f293d" }, ticks: { color: "#9ca3af" } },
                        x: { grid: { color: "#1f293d" }, ticks: { color: "#9ca3af" } }
                    },
                    plugins: {
                        legend: { labels: { color: "#9ca3af" } }
                    }
                }
            });
        }

        // 2. Camera Share Pie
        const cameraShareCtx = document.getElementById("cameraShareChart");
        if (cameraShareCtx) {
            new Chart(cameraShareCtx, {
                type: "pie",
                data: {
                    labels: Object.keys(res.camera_distribution),
                    datasets: [{
                        data: Object.values(res.camera_distribution),
                        backgroundColor: ["#3b82f6", "#06b6d4", "#f59e0b", "#8b5cf6"]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "bottom", labels: { color: "#9ca3af", font: { size: 10 } } }
                    }
                }
            });
        }

        // 3. Risk Classification Distribution Bar
        const riskDistCtx = document.getElementById("riskDistChart");
        if (riskDistCtx) {
            new Chart(riskDistCtx, {
                type: "bar",
                data: {
                    labels: Object.keys(res.risk_breakdown),
                    datasets: [{
                        label: "Logged Incidents",
                        data: Object.values(res.risk_breakdown),
                        backgroundColor: ["#10b981", "#f59e0b", "#f97316", "#ef4444"]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { grid: { color: "#1f293d" }, ticks: { color: "#9ca3af" } },
                        x: { grid: { display: false }, ticks: { color: "#9ca3af", font: { size: 10 } } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }

        // 4. Threats By Camera
        const threatsByCamCtx = document.getElementById("threatsByCamChart");
        if (threatsByCamCtx) {
            new Chart(threatsByCamCtx, {
                type: "bar",
                data: {
                    labels: ["CCTV-01", "CCTV-02", "CCTV-03", "CCTV-04"],
                    datasets: [{
                        label: "Active / Logged Anomalies",
                        data: [1, 1, 1, 1],
                        backgroundColor: "#8b5cf6"
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: { beginAtZero: true, grid: { color: "#1f293d" }, ticks: { color: "#9ca3af", stepSize: 1 } },
                        x: { grid: { display: false }, ticks: { color: "#9ca3af" } }
                    },
                    plugins: { legend: { display: false } }
                }
            });
        }
    } catch (err) {
        console.error("Analytics chart load error:", err);
    }
});
