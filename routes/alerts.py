from flask import Blueprint, request, jsonify, render_template
from database.mongo import db_manager
from alerts.emergency_dispatcher import emergency_dispatcher

alerts_bp = Blueprint("alerts", __name__)

@alerts_bp.route("/threats")
def threats_view():
    alerts = db_manager.get_alerts()
    critical_count = sum(1 for a in alerts if a.get("severity") == "CRITICAL" and a.get("status") in ("NEW", "ACKNOWLEDGED"))
    high_count = sum(1 for a in alerts if a.get("severity") == "HIGH" and a.get("status") in ("NEW", "ACKNOWLEDGED"))
    medium_count = sum(1 for a in alerts if a.get("severity") == "MEDIUM" and a.get("status") in ("NEW", "ACKNOWLEDGED"))
    resolved_count = sum(1 for a in alerts if a.get("severity") == "LOW" or a.get("status") in ("RESOLVED", "FALSE_POSITIVE"))
    
    return render_template(
        "threats.html",
        alerts=alerts,
        critical_count=critical_count,
        high_count=high_count,
        medium_count=medium_count,
        resolved_count=resolved_count
    )

@alerts_bp.route("/history")
def history_view():
    alerts = db_manager.get_alerts(limit=500)
    return render_template("history.html", alerts=alerts)

@alerts_bp.route("/api/alerts", methods=["GET"])
def get_alerts():
    camera_filter = request.args.get("camera_id")
    status_filter = request.args.get("status")
    severity_filter = request.args.get("severity")
    limit = int(request.args.get("limit", 100))

    alerts = db_manager.get_alerts(
        camera_id=camera_filter,
        severity=severity_filter,
        status=status_filter,
        limit=limit
    )

    return jsonify({
        "status": "success",
        "count": len(alerts),
        "database_connected": db_manager.is_connected(),
        "data": alerts
    })

@alerts_bp.route("/api/alerts", methods=["POST"])
def create_alert():
    payload = request.get_json() or {}
    if not payload.get("camera_id") or not payload.get("event_type"):
        return jsonify({"status": "error", "message": "camera_id and event_type are required"}), 400

    new_alert = db_manager.add_alert(payload)
    return jsonify({
        "status": "success",
        "message": "Alert logged successfully to MongoDB",
        "data": new_alert
    }), 201

@alerts_bp.route("/api/alerts/<event_id>/ack", methods=["POST"])
def acknowledge_alert(event_id):
    payload = request.get_json() or {}
    officer = payload.get("officer_name", "Officer on Duty")
    alert = db_manager.update_alert_status(event_id, "ACKNOWLEDGED", officer_name=officer)
    if alert:
        return jsonify({
            "status": "success",
            "message": f"Alert {event_id} acknowledged by {officer}",
            "data": alert
        })
    return jsonify({"status": "error", "message": "Alert not found"}), 404

@alerts_bp.route("/api/alerts/<event_id>/resolve", methods=["POST"])
def resolve_alert(event_id):
    alert = db_manager.update_alert_status(event_id, "RESOLVED")
    if alert:
        return jsonify({
            "status": "success",
            "message": f"Alert {event_id} marked as resolved",
            "data": alert
        })
    return jsonify({"status": "error", "message": "Alert not found"}), 404

@alerts_bp.route("/api/alerts/<event_id>/false_positive", methods=["POST"])
def false_positive_alert(event_id):
    alert = db_manager.update_alert_status(event_id, "FALSE_POSITIVE")
    if alert:
        return jsonify({
            "status": "success",
            "message": f"Alert {event_id} marked as false positive",
            "data": alert
        })
    return jsonify({"status": "error", "message": "Alert not found"}), 404

@alerts_bp.route("/api/alerts/active_emergency", methods=["GET"])
def get_active_emergency():
    active = emergency_dispatcher.get_active_emergency()
    return jsonify({
        "status": "success",
        "has_active_emergency": active is not None,
        "emergency": active
    })

@alerts_bp.route("/api/alerts/dispatch", methods=["POST"])
def dispatch_emergency_agency():
    payload = request.get_json() or {}
    event_id = payload.get("event_id")
    agency = payload.get("agency", "POLICE")
    notes = payload.get("notes", "")

    if not event_id:
        return jsonify({"status": "error", "message": "event_id is required"}), 400

    if agency.upper() == "ALL":
        result = emergency_dispatcher.dispatch_all(event_id)
    else:
        result = emergency_dispatcher.dispatch_agency(event_id, agency, officer_or_notes=notes)

    return jsonify({
        "status": "success",
        "message": f"Emergency {event_id} dispatched to {agency.upper()}",
        "result": result
    })

@alerts_bp.route("/api/alerts/simulate_threat", methods=["POST"])
def simulate_threat():
    payload = request.get_json() or {}
    threat_type = payload.get("threat_type", "GUN").upper()
    camera_id = payload.get("camera_id", "CCTV-01")

    threat_profiles = {
        "GUN": {
            "type": "WEAPON_FIREARM_DETECTED",
            "desc": "Armed subject detected carrying active firearm / handgun in surveillance zone.",
            "severity": "CRITICAL",
            "risk_score": 98,
            "bbox": [240, 160, 310, 240]
        },
        "ACCIDENT": {
            "type": "ACCIDENT_PEDESTRIAN_FALL",
            "desc": "Medical emergency: pedestrian collapse / heavy vehicular impact detected.",
            "severity": "HIGH",
            "risk_score": 85,
            "bbox": [180, 260, 360, 320]
        },
        "KILLING": {
            "type": "KILLING_VIOLENCE_DETECTED",
            "desc": "Lethal physical assault / violent altercation in progress.",
            "severity": "CRITICAL",
            "risk_score": 99,
            "bbox": [200, 140, 340, 310]
        },
        "CROWD_DISASTER": {
            "type": "CROWD_DISASTER_RISK",
            "desc": "Crowd disaster emergency: extreme surge, panic stampede, mass casualty hazard.",
            "severity": "CRITICAL",
            "risk_score": 95,
            "bbox": [100, 100, 540, 350]
        }
    }

    profile = threat_profiles.get(threat_type, threat_profiles["GUN"])
    emergency_event = emergency_dispatcher.create_emergency_event(
        threat_type=profile["type"],
        camera_id=camera_id,
        description=profile["desc"],
        location=f"Sector Terminal ({camera_id})",
        confidence=0.96,
        severity=profile["severity"],
        risk_score=profile["risk_score"],
        bbox=profile["bbox"]
    )

    return jsonify({
        "status": "success",
        "message": f"Emergency threat '{threat_type}' simulated successfully.",
        "data": emergency_event
    }), 201

@alerts_bp.route("/api/alerts/stop_emergency", methods=["POST"])
def stop_emergency():
    payload = request.get_json() or {}
    event_id = payload.get("event_id")
    result = emergency_dispatcher.stop_emergency(event_id)
    return jsonify({
        "status": "success",
        "message": "Emergency alert stopped and silenced.",
        "data": result
    })
