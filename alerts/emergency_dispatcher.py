import time
import logging
from datetime import datetime
from database.mongo import db_manager

logger = logging.getLogger("CrowdGuard.EmergencyDispatcher")

class EmergencyDispatcher:
    """
    Automated Multi-Agency Emergency Dispatch Coordinator.
    Manages urgent contact workflows to:
    1. POLICE: Law enforcement dispatch, armed threat alert, GPS coordinates.
    2. AMBULANCE: Medical EMS trauma unit, casualty triage, hospital routing.
    3. TV_CHANNEL: Public Emergency Broadcast System (EAS), media wire alert, sector evacuation crawl.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmergencyDispatcher, cls).__new__(cls)
            cls._instance._init_dispatcher()
        return cls._instance

    def _init_dispatcher(self):
        # In-memory dispatch tracking: {event_id: doc}
        self.dispatches = {}
        self.active_emergency = None

    def create_emergency_event(self, threat_type, camera_id="CCTV-01", description="", location="Sector 1", confidence=0.92, severity="CRITICAL", risk_score=90, bbox=None):
        """
        Creates and stores a high-priority emergency event requiring multi-agency response.
        """
        event_id = f"EMG-{int(time.time() * 1000) % 100000:05d}"
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        t_upper = str(threat_type).upper()
        if "GUN" in t_upper or "WEAPON" in t_upper or "KILLING" in t_upper or "VIOLENCE" in t_upper or "ASSAULT" in t_upper:
            primary_agencies = ["POLICE", "TV_CHANNEL", "AMBULANCE"]
        elif "ACCIDENT" in t_upper or "COLLAPSE" in t_upper or "FALL" in t_upper:
            primary_agencies = ["AMBULANCE", "POLICE"]
        elif "CROWD" in t_upper or "STAMPEDE" in t_upper or "SURGE" in t_upper:
            primary_agencies = ["POLICE", "AMBULANCE", "TV_CHANNEL"]
        else:
            primary_agencies = ["POLICE", "AMBULANCE"]

        emergency_doc = {
            "event_id": event_id,
            "camera_id": camera_id,
            "camera_name": f"Surveillance Node {camera_id}",
            "location": location,
            "event_type": t_upper,
            "severity": severity,
            "confidence": confidence,
            "risk_score": risk_score,
            "description": description or f"Critical incident flagged: {t_upper} at {location}",
            "timestamp": now_str,
            "status": "NEW",
            "target_agencies": primary_agencies,
            "dispatch_status": {agency: "PENDING" for agency in primary_agencies},
            "evidence_reference": f"{camera_id}_EMERGENCY_FRAME.jpg",
            "bbox": bbox
        }

        db_manager.add_alert(emergency_doc)
        self.dispatches[event_id] = emergency_doc
        self.active_emergency = emergency_doc
        logger.warning(f"EMERGENCY PROTOCOL ACTIVATED: {t_upper} on {camera_id}. Agencies: {primary_agencies}")
        return emergency_doc

    def dispatch_agency(self, event_id, agency_name, officer_or_notes=None):
        """
        Dispatches request to specific agency: POLICE, AMBULANCE, or TV_CHANNEL.
        """
        agency_name = agency_name.upper()
        doc = self.dispatches.get(event_id)
        if not doc:
            alerts = db_manager.get_alerts()
            doc = next((a for a in alerts if a.get("event_id") == event_id), None)
            if doc:
                self.dispatches[event_id] = doc

        if not doc:
            return {"success": False, "message": f"Event {event_id} not found"}

        d_status = doc.setdefault("dispatch_status", {})
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ref_code = f"{agency_name[:3]}-{int(time.time() * 100) % 10000:04d}"

        details = {
            "status": "DISPATCHED",
            "timestamp": now_str,
            "dispatch_code": ref_code,
            "notes": officer_or_notes or f"Automated emergency dispatch transmitted to {agency_name} Operations."
        }
        d_status[agency_name] = details

        db_manager.update_alert_status(event_id, status="ACKNOWLEDGED")
        logger.info(f"Emergency {event_id} dispatched to {agency_name} (Code: {ref_code})")
        return {
            "success": True,
            "event_id": event_id,
            "agency": agency_name,
            "details": details
        }

    def dispatch_all(self, event_id):
        """
        Instantly dispatches all required agencies for mass crisis response.
        """
        results = {}
        for ag in ["POLICE", "AMBULANCE", "TV_CHANNEL"]:
            results[ag] = self.dispatch_agency(event_id, ag)
        return results

    def stop_emergency(self, event_id=None):
        """
        Immediately stops active emergency alert, silences the alarm, and updates alert status to RESOLVED.
        Clears threat overlays on live camera streams.
        """
        self.active_emergency = None
        if event_id:
            db_manager.update_alert_status(event_id, "RESOLVED", officer_name="Operator Command (STOP)")
            if event_id in self.dispatches:
                self.dispatches[event_id]["status"] = "RESOLVED"
        else:
            alerts = db_manager.get_alerts()
            for a in alerts:
                if a.get("status") in ("NEW", "ACKNOWLEDGED"):
                    db_manager.update_alert_status(a.get("event_id"), "RESOLVED", officer_name="Operator Command (STOP)")

        # Clear overlays from camera streams
        try:
            from cameras.stream_manager import stream_manager
            stream_manager.clear_threat_overlays()
        except Exception as e:
            logger.debug(f"Stream overlay clear notice: {e}")

        logger.info(f"EMERGENCY PROTOCOL STOPPED: Alert {event_id or 'ALL'} silenced by operator.")
        return {"success": True, "message": "Emergency alert stopped and silenced."}

    def get_active_emergency(self):
        """
        Returns current active emergency event or None.
        Only returns un-resolved critical events.
        """
        if self.active_emergency and self.active_emergency.get("status") in ("NEW", "ACKNOWLEDGED"):
            return self.active_emergency
        alerts = db_manager.get_alerts(limit=1)
        if alerts and alerts[0].get("severity") == "CRITICAL" and alerts[0].get("status") in ("NEW", "ACKNOWLEDGED"):
            return alerts[0]
        return None

emergency_dispatcher = EmergencyDispatcher()
