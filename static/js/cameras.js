// CROWDGUARD AI - Camera Grid & Laptop Camera Stream Management

let activeLaptopCameraId = "CCTV-01";
let behaviourPollInterval = null;
let browserWebcamStream = null;
let browserWebcamInterval = null;

document.addEventListener("DOMContentLoaded", function () {
    // Check laptop webcam status and start polling active node
    checkLaptopHardwareStatus();
    startBehaviourPolling(activeLaptopCameraId);
    startGridPolling();
});

// Check hardware accessibility of laptop webcam
async function checkLaptopHardwareStatus() {
    try {
        const response = await fetch("/api/cameras/laptop/status");
        if (!response.ok) return;
        const res = await response.json();
        
        const badge = document.getElementById("laptop-cam-status-badge");
        if (badge) {
            if (res.hardware_test && res.hardware_test.available) {
                badge.className = "badge bg-success";
                badge.innerHTML = '<i class="fa-solid fa-circle text-light me-1"></i> LAPTOP WEBCAM READY';
            } else {
                badge.className = "badge bg-info text-dark";
                badge.innerHTML = '<i class="fa-solid fa-circle-check me-1"></i> SIMULATED / WEBCAM READY';
            }
        }
    } catch (err) {
        console.warn("Laptop webcam status check:", err);
    }
}

// Toggle Laptop Camera Console
function toggleLaptopConsole() {
    const consoleCard = document.getElementById("laptop-camera-console-card");
    if (consoleCard) {
        if (consoleCard.style.display === "none") {
            consoleCard.style.display = "block";
            consoleCard.scrollIntoView({ behavior: "smooth" });
        } else {
            consoleCard.scrollIntoView({ behavior: "smooth" });
        }
    }
}

// Connect Host Laptop Camera (Device 0)
async function activateLaptopWebcam(cameraId = "CCTV-01", devIndex = 0) {
    activeLaptopCameraId = cameraId;
    const badgeNode = document.getElementById("active-laptop-node-badge");
    const hudNode = document.getElementById("hud-camera-id");
    const fullHudBtn = document.getElementById("btn-full-hud");
    const statusBadge = document.getElementById("laptop-cam-status-badge");
    const sourceLabel = document.getElementById("stream-source-label");

    if (badgeNode) badgeNode.innerText = `NODE: ${cameraId}`;
    if (hudNode) hudNode.innerText = cameraId;
    if (fullHudBtn) fullHudBtn.href = `/camera/${cameraId}`;
    if (sourceLabel) sourceLabel.innerText = `SOURCE: Laptop Webcam (Device ${devIndex})`;

    if (statusBadge) {
        statusBadge.className = "badge bg-warning text-dark";
        statusBadge.innerHTML = '<i class="fa-solid fa-spinner fa-spin me-1"></i> CONNECTING WEBCAM...';
    }

    // Stop browser stream if running
    if (browserWebcamStream) {
        stopBrowserWebcam();
    }

    try {
        const response = await fetch("/api/cameras/laptop/activate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ camera_id: cameraId, device_index: devIndex })
        });
        const res = await response.json();

        if (res.status === "success") {
            if (statusBadge) {
                statusBadge.className = "badge bg-success";
                statusBadge.innerHTML = `<i class="fa-solid fa-circle text-light me-1"></i> WEBCAM (DEV ${devIndex}) ACTIVE`;
            }
            const modeLabel = document.getElementById("hud-stream-mode");
            if (modeLabel) modeLabel.innerText = "HARDWARE WEBCAM ACTIVE";
            const fpsBadge = document.getElementById("stream-fps-badge");
            if (fpsBadge) fpsBadge.innerText = "FPS: 30.0 | AI: YOLOv11 Active";
            reloadStreamImage();
            startBehaviourPolling(cameraId);
        } else {
            if (statusBadge) {
                statusBadge.className = "badge bg-danger";
                statusBadge.innerText = "WEBCAM ERROR";
            }
            alert("Webcam connection notice: " + (res.message || "Failed to activate"));
        }
    } catch (err) {
        console.error("Failed to activate laptop camera:", err);
        if (statusBadge) {
            statusBadge.className = "badge bg-danger";
            statusBadge.innerText = "CONNECT FAILED";
        }
    }
}

// Toggle Client-Side Browser Webcam Stream (WebRTC -> Backend Ingestion)
async function toggleBrowserWebcam(cameraId = "CCTV-01") {
    const btn = document.getElementById("btn-browser-webcam");
    const video = document.getElementById("browser-webcam-video");
    const canvas = document.getElementById("browser-webcam-canvas");
    const streamImg = document.getElementById("laptop-cam-stream-img");
    const statusBadge = document.getElementById("laptop-cam-status-badge");
    const modeLabel = document.getElementById("hud-stream-mode");

    if (browserWebcamStream) {
        // Stop browser webcam
        stopBrowserWebcam();
        if (btn) {
            btn.className = "btn btn-outline-success btn-sm fw-bold";
            btn.innerHTML = '<i class="fa-solid fa-globe me-1"></i> Browser Webcam Mode';
        }
        if (video) video.style.display = "none";
        if (streamImg) streamImg.style.display = "block";
        if (modeLabel) modeLabel.innerText = "HARDWARE CAPTURE ACTIVE";
        if (statusBadge) {
            statusBadge.className = "badge bg-success";
            statusBadge.innerHTML = '<i class="fa-solid fa-circle text-light me-1"></i> WEBCAM CONNECTED';
        }
        reloadStreamImage();
    } else {
        // Request Browser Webcam
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 1280 }, height: { ideal: 720 } },
                audio: false
            });
            browserWebcamStream = stream;

            if (video) {
                video.srcObject = stream;
                video.style.display = "block";
                video.style.zIndex = "4";
            }
            if (streamImg) {
                streamImg.style.display = "none";
            }

            if (btn) {
                btn.className = "btn btn-danger btn-sm fw-bold";
                btn.innerHTML = '<i class="fa-solid fa-stop me-1"></i> Stop Browser Webcam';
            }
            if (modeLabel) modeLabel.innerText = "BROWSER WEBRTC INGESTION ACTIVE";
            if (statusBadge) {
                statusBadge.className = "badge bg-info text-dark";
                statusBadge.innerHTML = '<i class="fa-solid fa-satellite-dish me-1"></i> STREAMING TO AI ENGINE';
            }

            // Ingest frames continuously to server AI behaviour engine (~10 FPS)
            const ctx = canvas.getContext("2d");
            canvas.width = 640;
            canvas.height = 480;

            browserWebcamInterval = setInterval(async () => {
                if (!browserWebcamStream || !video.videoWidth) return;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
                const b64Data = canvas.toDataURL("image/jpeg", 0.7);

                try {
                    await fetch(`/api/cameras/${cameraId}/ingest_frame`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ frame: b64Data })
                    });
                } catch (e) {
                    // silently handle intermittent frame drop
                }
            }, 100);

            startBehaviourPolling(cameraId);
        } catch (err) {
            alert("Could not access browser webcam: " + err.message + "\nPlease verify camera permissions in your browser.");
        }
    }
}

function stopBrowserWebcam() {
    if (browserWebcamStream) {
        browserWebcamStream.getTracks().forEach(t => t.stop());
        browserWebcamStream = null;
    }
    if (browserWebcamInterval) {
        clearInterval(browserWebcamInterval);
        browserWebcamInterval = null;
    }
    const video = document.getElementById("browser-webcam-video");
    if (video) {
        video.srcObject = null;
        video.style.display = "none";
    }
    const streamImg = document.getElementById("laptop-cam-stream-img");
    if (streamImg) {
        streamImg.style.display = "block";
        streamImg.style.opacity = "1";
    }
}

// Start Real-Time Behaviour Anomaly Log Polling
function startBehaviourPolling(cameraId) {
    if (behaviourPollInterval) clearInterval(behaviourPollInterval);

    fetchCameraBehaviour(cameraId);
    behaviourPollInterval = setInterval(() => {
        fetchCameraBehaviour(cameraId);
    }, 1200);
}

let lastBehaviourHash = "";
async function fetchCameraBehaviour(cameraId) {
    try {
        const response = await fetch(`/api/cameras/${encodeURIComponent(cameraId)}/behaviour`);
        if (!response.ok) return;
        const data = await response.json();

        if (data.status === "success") {
            // Update Active Person Count (Real-Time)
            const countEl = document.getElementById("laptop-live-count");
            if (countEl) countEl.innerText = `${data.people_count} Persons`;

            // Update Motion Detection KPI
            const motionEl = document.getElementById("laptop-live-motion");
            if (motionEl) {
                if (data.motion_count > 0 || data.motion_status === "MOTION DETECTED") {
                    motionEl.className = "fs-6 fw-bold text-success font-monospace mt-1";
                    motionEl.innerHTML = `<i class="fa-solid fa-person-walking me-1"></i> DETECTED (${data.motion_count || 1} Moving)`;
                } else {
                    motionEl.className = "fs-6 fw-bold text-secondary font-monospace mt-1";
                    motionEl.innerHTML = `<i class="fa-solid fa-person me-1"></i> STATIONARY (Idle)`;
                }
            }

            // Update HUD Person & Motion Pill
            const hudPersonCount = document.getElementById("hud-person-count-display");
            if (hudPersonCount) {
                const motionText = (data.motion_count > 0 || data.motion_status === "MOTION DETECTED") ?
                    `MOTION: DETECTED (${data.motion_count || 1} MOVING)` : `MOTION: STATIONARY (IDLE)`;
                hudPersonCount.innerText = `REAL-TIME COUNT: ${data.people_count} PERSONS | ${motionText}`;
            }

            // Update Risk Badge
            const riskEl = document.getElementById("laptop-live-risk");
            if (riskEl) {
                riskEl.innerText = `${data.risk_level} (${data.risk_score}/100)`;
                riskEl.className = "fs-6 fw-bold font-monospace mt-1 " + (
                    data.risk_level === "CRITICAL" ? "text-danger" :
                    data.risk_level === "HIGH" ? "text-warning" :
                    data.risk_level === "MEDIUM" ? "text-info" : "text-success"
                );
            }

            // Update FPS
            const fpsBadge = document.getElementById("stream-fps-badge");
            if (fpsBadge && data.fps) {
                fpsBadge.innerText = `FPS: ${data.fps} | AI: YOLO + ByteTrack + BehaviourEngine`;
            }

            // Update Behaviour Anomaly Events Ticker without arbitrary track IDs
            const ticker = document.getElementById("laptop-behaviour-ticker");
            if (ticker) {
                const events = data.events || [];
                const currentHash = JSON.stringify(events) + data.people_count + (data.motion_count || 0);
                if (currentHash !== lastBehaviourHash) {
                    lastBehaviourHash = currentHash;
                    ticker.innerHTML = "";

                    if (events.length > 0) {
                        events.slice(0, 10).forEach(evt => {
                            const bType = evt.behaviour_type || "ANOMALY";
                            const riskWeight = evt.risk_weight || 15;
                            const isHigh = riskWeight >= 25;
                            const cleanDesc = (evt.description || 'Movement anomaly detected.').replace(/Track\s*#\d+/gi, 'Identified Person');

                            const itemDiv = document.createElement("div");
                            itemDiv.className = "p-2 rounded bg-dark border " + (isHigh ? "border-danger" : "border-warning");
                            itemDiv.style.fontSize = "0.78rem";
                            itemDiv.innerHTML = `
                                <div class="d-flex justify-content-between mb-1">
                                    <span class="badge ${isHigh ? 'bg-danger' : 'bg-warning text-dark'}">${bType.replace(/_/g, ' ')}</span>
                                    <span class="text-cyan font-monospace">COUNT: ${data.people_count} PERSONS</span>
                                </div>
                                <div class="text-light fw-bold">${cleanDesc}</div>
                                <div class="text-dim mt-1" style="font-size: 0.72rem;">Confidence: ${(evt.confidence * 100).toFixed(0)}% | Risk Weight: ${riskWeight}</div>
                            `;
                            ticker.appendChild(itemDiv);
                        });
                    } else {
                        const statusDesc = data.motion_count > 0 ?
                            `Tracking ${data.people_count} person(s) - Motion detected (${data.motion_count} active).` :
                            `Tracking ${data.people_count} person(s) - Flow stationary.`;
                        ticker.innerHTML = `
                            <div class="p-2 rounded bg-dark border border-secondary" style="font-size: 0.78rem;">
                                <div class="d-flex justify-content-between text-muted mb-1">
                                    <span class="text-cyan font-monospace">MONITORING</span>
                                    <span>Just Now</span>
                                </div>
                                <div class="text-info fw-bold">STREAM ACTIVE - REAL-TIME COUNT: ${data.people_count} PERSONS</div>
                                <div class="text-dim">${statusDesc}</div>
                            </div>
                        `;
                    }
                }
            }
        }
    } catch (err) {
        // network error
    }
}

// Real-Time Grid Telemetry Poller for All Camera Cards
let gridPollInterval = null;
function startGridPolling() {
    if (gridPollInterval) clearInterval(gridPollInterval);
    fetchGridTelemetry();
    gridPollInterval = setInterval(fetchGridTelemetry, 1500);
}

async function fetchGridTelemetry() {
    try {
        const res = await fetch("/api/cameras");
        if (!res.ok) return;
        const json = await res.json();
        if (json.status === "success" && Array.isArray(json.data)) {
            json.data.forEach(cam => {
                const countEl = document.getElementById(`grid-count-${cam.camera_id}`);
                if (countEl && cam.people_count !== undefined) {
                    countEl.innerText = `${cam.people_count} Persons`;
                }

                const motionEl = document.getElementById(`grid-motion-${cam.camera_id}`);
                if (motionEl) {
                    if (cam.motion_count > 0 || cam.motion_status === "MOTION DETECTED") {
                        motionEl.className = "badge bg-dark border border-success text-success font-monospace";
                        motionEl.innerHTML = `<i class="fa-solid fa-person-walking me-1"></i>Active (${cam.motion_count || 1} Moving)`;
                    } else {
                        motionEl.className = "badge bg-dark border border-secondary text-secondary font-monospace";
                        motionEl.innerHTML = `<i class="fa-solid fa-person me-1"></i>Stationary`;
                    }
                }

                const riskEl = document.getElementById(`grid-risk-${cam.camera_id}`);
                if (riskEl && cam.risk_level) {
                    riskEl.innerText = cam.risk_level;
                }
            });
        }
    } catch (e) {
        // ignore intermittent network drop
    }
}

// Multi-Modal LLM Vision Scan on Laptop Camera
async function runLLMVisionScan(cameraId = "CCTV-01") {
    const modalEl = document.getElementById("llmVisionModal");
    const countEl = document.getElementById("modal-llm-person-count");
    const riskEl = document.getElementById("modal-llm-risk-items");
    const scoreEl = document.getElementById("modal-llm-risk-score");
    const summaryEl = document.getElementById("modal-llm-summary");
    const tbody = document.getElementById("modal-llm-items-tbody");

    if (countEl) countEl.innerText = "--";
    if (riskEl) riskEl.innerText = "--";
    if (scoreEl) scoreEl.innerText = "--";
    if (summaryEl) summaryEl.innerHTML = '<span class="text-warning"><i class="fa-solid fa-spinner fa-spin me-1"></i> Running Multi-Modal LLM Vision forensic analysis on laptop camera frame...</span>';
    if (tbody) tbody.innerHTML = '<tr><td colspan="3" class="text-center text-muted">Analyzing...</td></tr>';

    const bsModal = bootstrap.Modal.getOrCreateInstance(modalEl);
    bsModal.show();

    try {
        const response = await fetch("/api/llm_analyze_frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ camera_id: cameraId })
        });
        const res = await response.json();

        if (countEl) countEl.innerText = res.person_count !== undefined ? res.person_count : 0;
        if (riskEl) riskEl.innerText = (res.risk_items || []).length;
        if (scoreEl) scoreEl.innerText = `${res.risk_score || 0}/100`;
        if (summaryEl) summaryEl.innerText = res.forensic_summary || "Visual frame audit completed successfully.";

        if (tbody) {
            tbody.innerHTML = "";
            const items = res.risk_items || [];
            if (items.length > 0) {
                items.forEach(it => {
                    const tr = document.createElement("tr");
                    tr.innerHTML = `
                        <td class="text-danger fw-bold"><i class="fa-solid fa-triangle-exclamation me-1"></i>${(it.item_type || 'WEAPON').toUpperCase()}</td>
                        <td class="text-cyan font-monospace">${((it.confidence || 0.85) * 100).toFixed(0)}%</td>
                        <td class="text-light">${it.description || 'Spatial risk flagged by LLM Vision'}</td>
                    `;
                    tbody.appendChild(tr);
                });
            } else {
                tbody.innerHTML = '<tr><td colspan="3" class="text-center text-success"><i class="fa-solid fa-shield-check me-1"></i> No lethal weapons or risk objects detected in frame.</td></tr>';
            }
        }
    } catch (err) {
        if (summaryEl) summaryEl.innerHTML = `<span class="text-danger">LLM Scan error: ${err}</span>`;
    }
}

// Reload Stream Image with cache bust
function reloadStreamImage() {
    const img = document.getElementById("laptop-cam-stream-img");
    if (img) {
        img.src = `/api/cameras/${activeLaptopCameraId}/stream?t=` + Date.now();
    }
}

function handleStreamImageError() {
    const img = document.getElementById("laptop-cam-stream-img");
    if (img) {
        setTimeout(() => {
            img.src = `/api/cameras/${activeLaptopCameraId}/stream?t=` + Date.now();
        }, 1500);
    }
}

// Preset Auto-Fill for Register Camera Modal
function autoFillLaptopWebcam() {
    document.getElementById("new-cam-name").value = "Laptop Webcam Node";
    document.getElementById("new-cam-loc").value = "Local Workstation Station";
    document.getElementById("new-cam-type").value = "Webcam";
    document.getElementById("new-cam-fps").value = 30;
    document.getElementById("new-cam-url").value = "0";
}

// Register New Camera
async function submitNewCamera() {
    const name = document.getElementById("new-cam-name").value.trim();
    const location = document.getElementById("new-cam-loc").value.trim();
    const sourceType = document.getElementById("new-cam-type").value;
    const fps = parseInt(document.getElementById("new-cam-fps").value) || 30;
    const streamUrl = document.getElementById("new-cam-url").value.trim();

    if (!name || !location || !streamUrl) {
        alert("Please complete all required fields.");
        return;
    }

    try {
        const response = await fetch("/api/cameras", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                name: name,
                location: location,
                source_type: sourceType,
                fps_limit: fps,
                stream_url: streamUrl
            })
        });
        const res = await response.json();
        if (res.status === "success") {
            window.location.reload();
        } else {
            alert("Error: " + res.message);
        }
    } catch (err) {
        alert("Failed to create camera: " + err);
    }
}

// Delete Camera
async function deleteCamera(cameraId) {
    if (!confirm(`Are you sure you want to remove node ${cameraId}?`)) return;

    try {
        const response = await fetch(`/api/cameras/${cameraId}`, {
            method: "DELETE"
        });
        const res = await response.json();
        if (res.status === "success") {
            const row = document.getElementById(`cam-row-${cameraId}`);
            if (row) row.remove();
            window.location.reload();
        }
    } catch (err) {
        alert("Failed to delete camera: " + err);
    }
}
