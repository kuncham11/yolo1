// CrowdGuard AI - Threat Center & Multi-Agency Emergency Dispatch Coordinator

let currentEmergencyEventId = null;
let emergencyModalInstance = null;
let lastSeenEmergencyId = null;
let audioCtx = null;

// Synthesize high-urgency two-tone alarm siren using Web Audio API
let activeOscillator = null;
let activeGainNode = null;
let isAlarmSilenced = false;

function playEmergencyAlarm() {
    if (isAlarmSilenced) return;
    try {
        if (!audioCtx) {
            audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        }
        if (audioCtx.state === 'suspended') {
            audioCtx.resume();
        }

        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sawtooth";

        const now = audioCtx.currentTime;
        // Two-tone siren alternating 880Hz and 660Hz
        osc.frequency.setValueAtTime(880, now);
        osc.frequency.setValueAtTime(660, now + 0.18);
        osc.frequency.setValueAtTime(880, now + 0.36);
        osc.frequency.setValueAtTime(660, now + 0.54);

        gain.gain.setValueAtTime(0.18, now);
        gain.gain.exponentialRampToValueAtTime(0.01, now + 0.72);

        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start(now);
        osc.stop(now + 0.72);

        activeOscillator = osc;
        activeGainNode = gain;
    } catch (e) {
        console.warn("Web Audio alarm error:", e);
    }
}

function silenceAudioAlarm() {
    isAlarmSilenced = true;
    try {
        if (activeGainNode && audioCtx) {
            activeGainNode.gain.setValueAtTime(0, audioCtx.currentTime);
        }
        if (activeOscillator) {
            activeOscillator.stop();
            activeOscillator = null;
        }
        if (audioCtx && audioCtx.state === 'running') {
            audioCtx.suspend();
        }
    } catch (e) {
        console.warn("Error silencing audio:", e);
    }
}

async function ackThreat(eventId) {
    try {
        const response = await fetch(`/api/alerts/${eventId}/ack`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ officer_name: "Security Supervisor" })
        });
        const res = await response.json();
        if (res.status === "success") {
            const badge = document.getElementById(`threat-status-${eventId}`);
            if (badge) {
                badge.className = "badge bg-warning text-dark";
                badge.innerText = "ACKNOWLEDGED";
            }
        }
    } catch (err) {
        alert("Failed to acknowledge threat: " + err);
    }
}

async function resolveThreat(eventId) {
    try {
        const response = await fetch(`/api/alerts/${eventId}/resolve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const res = await response.json();
        if (res.status === "success") {
            const badge = document.getElementById(`threat-status-${eventId}`);
            if (badge) {
                badge.className = "badge bg-success";
                badge.innerText = "RESOLVED";
            }
        }
    } catch (err) {
        alert("Failed to resolve threat: " + err);
    }
}

async function falsePositiveThreat(eventId) {
    try {
        const response = await fetch(`/api/alerts/${eventId}/false_positive`, {
            method: "POST",
            headers: { "Content-Type": "application/json" }
        });
        const res = await response.json();
        if (res.status === "success") {
            const badge = document.getElementById(`threat-status-${eventId}`);
            if (badge) {
                badge.className = "badge bg-secondary";
                badge.innerText = "FALSE POSITIVE";
            }
        }
    } catch (err) {
        alert("Failed to mark false positive: " + err);
    }
}

// Multi-Agency Emergency Dispatch Functions
async function dispatchEmergency(agency) {
    if (!currentEmergencyEventId) {
        alert("No active emergency event selected for dispatch.");
        return;
    }

    try {
        const response = await fetch("/api/alerts/dispatch", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                event_id: currentEmergencyEventId,
                agency: agency,
                notes: `Manual command dispatch authorization by Security Supervisor.`
            })
        });

        const res = await response.json();
        if (res.status === "success") {
            updateAgencyBadge(agency, "DISPATCHED");
            playEmergencyAlarm();
        } else {
            alert("Dispatch failed: " + (res.message || "Unknown error"));
        }
    } catch (err) {
        alert("Error sending emergency dispatch: " + err);
    }
}

function updateAgencyBadge(agency, status) {
    const targetAgencies = agency === "ALL" ? ["POLICE", "AMBULANCE", "TV_CHANNEL"] : [agency.toUpperCase()];

    targetAgencies.forEach(ag => {
        const badge = document.getElementById(`dispatch-status-${ag}`);
        const btn = document.getElementById(`btn-dispatch-${ag}`);
        if (badge) {
            badge.className = "badge bg-success font-monospace px-2 py-1";
            badge.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> DISPATCHED`;
        }
        if (btn) {
            btn.className = "btn btn-outline-success btn-sm w-100 disabled";
            btn.innerHTML = `<i class="fa-solid fa-check me-1"></i> Dispatched to ${ag}`;
        }
    });
}

let activeEmergencyData = null;

// Threat Simulation Drill Trigger
async function simulateThreat(threatType, cameraId = "CCTV-01") {
    try {
        isAlarmSilenced = false;
        const response = await fetch("/api/alerts/simulate_threat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                threat_type: threatType,
                camera_id: cameraId
            })
        });

        const res = await response.json();
        if (res.status === "success" && res.data) {
            currentEmergencyEventId = res.data.event_id;
            lastSeenEmergencyId = res.data.event_id;
            try {
                sessionStorage.removeItem("silenced_alert_" + res.data.event_id);
            } catch (e) {}

            // Activate crisis alert indicator WITHOUT popping up modal on screen
            setActiveCrisisAlert(res.data);
            playEmergencyAlarm();
        } else {
            alert("Simulation failed: " + (res.message || "Unknown error"));
        }
    } catch (err) {
        alert("Failed to simulate threat: " + err);
    }
}

// STOP EMERGENCY ALERT - Operator Command
async function stopEmergencyAlert(eventId = null) {
    const targetId = eventId || currentEmergencyEventId;
    isAlarmSilenced = true;

    // 1. Immediately silence any active audio
    silenceAudioAlarm();

    // 2. Hide crisis alert button and global stop button
    const crisisBtnContainer = document.getElementById("crisis-alert-button-container");
    if (crisisBtnContainer) {
        crisisBtnContainer.style.display = "none";
    }
    const topbarStopBtn = document.getElementById("global-stop-alert-container");
    if (topbarStopBtn) {
        topbarStopBtn.style.display = "none";
    }
    const camPill = document.getElementById("cam-crisis-alert-pill");
    if (camPill) {
        camPill.style.display = "none";
    }

    // 3. Close the modal if open
    if (emergencyModalInstance) {
        emergencyModalInstance.hide();
    }
    const modalEl = document.getElementById("emergencyDispatchModal");
    if (modalEl && typeof bootstrap !== "undefined") {
        const bsModal = bootstrap.Modal.getInstance(modalEl);
        if (bsModal) bsModal.hide();
    }

    // 4. Remember that this alert was stopped/silenced so we don't alert repeatedly
    if (targetId) {
        try {
            sessionStorage.setItem("silenced_alert_" + targetId, "true");
        } catch (e) {}
    }
    lastSeenEmergencyId = targetId || "STOPPED";
    currentEmergencyEventId = null;
    activeEmergencyData = null;

    // 5. Notify backend to clear emergency state and camera threat overlays
    try {
        await fetch("/api/alerts/stop_emergency", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ event_id: targetId })
        });
    } catch (e) {
        console.warn("Failed to notify server of emergency stop:", e);
    }

    // 6. Update threat status badge in table if visible
    if (targetId) {
        const badge = document.getElementById(`threat-status-${targetId}`);
        if (badge) {
            badge.className = "badge bg-success";
            badge.innerText = "STOPPED / RESOLVED";
        }
    }
}

// Populates modal elements with emergency data WITHOUT showing modal on screen
function populateEmergencyModalFields(data) {
    if (!data) return;
    const modalEl = document.getElementById("emergencyDispatchModal");
    if (!modalEl) return;

    // Populate modal fields
    const idEl = document.getElementById("modal-emg-id");
    if (idEl) idEl.innerText = data.event_id || "EMG-00000";

    const typeEl = document.getElementById("modal-emg-type");
    if (typeEl) typeEl.innerText = (data.event_type || "SECURITY THREAT").replace(/_/g, ' ');

    const camEl = document.getElementById("modal-emg-camera");
    if (camEl) camEl.innerText = `${data.camera_id} (${data.location || 'Surveillance Node'})`;

    const timeEl = document.getElementById("modal-emg-time");
    if (timeEl) timeEl.innerText = data.timestamp || new Date().toLocaleTimeString();

    const descEl = document.getElementById("modal-emg-desc");
    if (descEl) descEl.innerText = data.description || "Urgent emergency detected requiring immediate multi-agency response.";

    // Reset agency buttons & status badges
    ["POLICE", "AMBULANCE", "TV_CHANNEL"].forEach(ag => {
        const badge = document.getElementById(`dispatch-status-${ag}`);
        const btn = document.getElementById(`btn-dispatch-${ag}`);
        const isDispatched = data.dispatch_status && data.dispatch_status[ag] && data.dispatch_status[ag].status === "DISPATCHED";

        if (badge) {
            if (isDispatched) {
                badge.className = "badge bg-success font-monospace px-2 py-1";
                badge.innerHTML = `<i class="fa-solid fa-circle-check me-1"></i> DISPATCHED`;
            } else {
                badge.className = "badge bg-danger font-monospace px-2 py-1";
                badge.innerHTML = `<i class="fa-solid fa-clock me-1"></i> PENDING`;
            }
        }
        if (btn) {
            if (isDispatched) {
                btn.className = "btn btn-outline-success btn-sm w-100 disabled";
                btn.innerHTML = `<i class="fa-solid fa-check me-1"></i> Dispatched to ${ag}`;
            } else {
                const btnClass = ag === "POLICE" ? "btn-danger" : (ag === "AMBULANCE" ? "btn-warning" : "btn-info");
                btn.className = `btn ${btnClass} btn-sm w-100 fw-bold`;
                btn.innerHTML = `<i class="fa-solid fa-phone me-1"></i> Dispatch ${ag}`;
            }
        }
    });
}

// Activates the crisis alert indicators on topbar/camera WITHOUT popping up on screen
function setActiveCrisisAlert(data) {
    if (!data) return;
    activeEmergencyData = data;
    currentEmergencyEventId = data.event_id;

    // Pre-populate modal fields so they are ready when the user presses the alert button
    populateEmergencyModalFields(data);

    // Show the CRITICAL SURVEILLANCE CRISIS ALERT button in topbar
    const crisisBtnContainer = document.getElementById("crisis-alert-button-container");
    if (crisisBtnContainer) {
        crisisBtnContainer.style.display = "block";
    }

    const typeBadge = document.getElementById("topbar-crisis-threat-type");
    if (typeBadge) {
        typeBadge.innerText = (data.event_type || "CRISIS").replace(/_/g, ' ');
    }

    // Show global stop button
    const topbarStopBtn = document.getElementById("global-stop-alert-container");
    if (topbarStopBtn) {
        topbarStopBtn.style.display = "block";
    }

    // Show camera crisis pill if present
    const camPill = document.getElementById("cam-crisis-alert-pill");
    if (camPill) {
        camPill.style.display = "inline-block";
    }

    // Notice: DOES NOT CALL emergencyModalInstance.show()
    // The screen remains completely unblocked until user presses CRITICAL SURVEILLANCE CRISIS ALERT!
}

// USER EXPLICIT ACTION: Opens the emergency modal when the user presses CRITICAL SURVEILLANCE CRISIS ALERT
function openActiveEmergencyModal() {
    const modalEl = document.getElementById("emergencyDispatchModal");
    if (!modalEl) return;

    if (activeEmergencyData) {
        populateEmergencyModalFields(activeEmergencyData);
    }

    if (!emergencyModalInstance && typeof bootstrap !== "undefined") {
        emergencyModalInstance = new bootstrap.Modal(modalEl);
    }
    if (emergencyModalInstance) {
        emergencyModalInstance.show();
    }
}

// Direct click from table row (e.g. Contact button)
function openEmergencyModalWithData(data) {
    activeEmergencyData = data;
    currentEmergencyEventId = data.event_id;
    populateEmergencyModalFields(data);

    const modalEl = document.getElementById("emergencyDispatchModal");
    if (!modalEl) return;

    if (!emergencyModalInstance && typeof bootstrap !== "undefined") {
        emergencyModalInstance = new bootstrap.Modal(modalEl);
    }
    if (emergencyModalInstance) {
        emergencyModalInstance.show();
    }
}

// Background poller for active emergencies - NEVER pops up modal automatically
async function pollActiveEmergencies() {
    try {
        const response = await fetch("/api/alerts/active_emergency");
        const res = await response.json();
        const crisisBtnContainer = document.getElementById("crisis-alert-button-container");
        const topbarStopBtn = document.getElementById("global-stop-alert-container");
        const camPill = document.getElementById("cam-crisis-alert-pill");

        if (res.status === "success" && res.has_active_emergency && res.emergency) {
            const emg = res.emergency;
            let isSilenced = false;
            try {
                isSilenced = sessionStorage.getItem("silenced_alert_" + emg.event_id) === "true";
            } catch (e) {}

            if (!isSilenced && emg.status === "NEW") {
                // Show the CRITICAL SURVEILLANCE CRISIS ALERT button, do NOT pop up modal!
                setActiveCrisisAlert(emg);

                if (emg.event_id !== lastSeenEmergencyId) {
                    lastSeenEmergencyId = emg.event_id;
                    playEmergencyAlarm();
                }
            } else {
                if (crisisBtnContainer) crisisBtnContainer.style.display = "none";
                if (topbarStopBtn) topbarStopBtn.style.display = "none";
                if (camPill) camPill.style.display = "none";
            }
        } else {
            if (crisisBtnContainer) crisisBtnContainer.style.display = "none";
            if (topbarStopBtn) topbarStopBtn.style.display = "none";
            if (camPill) camPill.style.display = "none";
        }
    } catch (e) {
        // Silently continue polling
    }
}

// Start polling on DOM load
document.addEventListener("DOMContentLoaded", () => {
    setInterval(pollActiveEmergencies, 3000);
});

