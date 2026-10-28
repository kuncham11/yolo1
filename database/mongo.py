import os
import logging
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from config import Config

logger = logging.getLogger("CrowdGuard.Database")

# Clean slate: zero default/mock cameras or alerts
INITIAL_CAMERAS = []
INITIAL_ALERTS = []

class DatabaseManager:
    """
    Enterprise MongoDB persistence manager for CrowdGuard AI.
    Includes automated schema setup, index creation, and seamless in-memory fallback.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DatabaseManager, cls).__new__(cls)
            cls._instance._init_connection()
        return cls._instance

    def _init_connection(self):
        self.client = None
        self.db = None
        self.connected = False
        self._memory_cameras = list(INITIAL_CAMERAS)
        self._memory_alerts = list(INITIAL_ALERTS)
        self._memory_behaviour = []
        self._memory_detections = []

        try:
            mongo_uri = Config.MONGO_URI
            db_name = Config.MONGO_DB_NAME
            # Fast failover with 1.5s timeout for resilient startup
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=1500)
            self.client.admin.command('ping')
            self.db = self.client[db_name]
            self.connected = True
            logger.info(f"MongoDB connected successfully to '{db_name}' at {mongo_uri}")
            self._ensure_indexes()
            self._seed_default_data()
        except (ConnectionFailure, ServerSelectionTimeoutError, Exception) as e:
            self.connected = False
            logger.warning(f"MongoDB connection failed: {e}. Operating in graceful in-memory storage mode.")

    def _ensure_indexes(self):
        if not self.connected or self.db is None:
            return
        try:
            # Cameras collection indexes
            self.db.cameras.create_index([("camera_id", ASCENDING)], unique=True)
            self.db.cameras.create_index([("status", ASCENDING)])

            # Alerts collection indexes
            self.db.alerts.create_index([("event_id", ASCENDING)], unique=True)
            self.db.alerts.create_index([("camera_id", ASCENDING)])
            self.db.alerts.create_index([("timestamp", DESCENDING)])
            self.db.alerts.create_index([("event_type", ASCENDING)])
            self.db.alerts.create_index([("severity", ASCENDING)])
            self.db.alerts.create_index([("status", ASCENDING)])

            # Behaviour events collection indexes
            self.db.behaviour_events.create_index([("camera_id", ASCENDING)])
            self.db.behaviour_events.create_index([("start_time", DESCENDING)])
            self.db.behaviour_events.create_index([("behaviour_type", ASCENDING)])

            # Detections collection indexes
            self.db.detections.create_index([("camera_id", ASCENDING)])
            self.db.detections.create_index([("timestamp", DESCENDING)])
            logger.info("MongoDB indexes verified.")
        except Exception as e:
            logger.error(f"Error creating indexes: {e}")

    def _seed_default_data(self):
        # Default seed disabled: Starting with clean slate (0 cameras, 0 alerts)
        pass

    def clear_all_data(self):
        """Removes all stored cameras, alerts, behaviour events, and detections."""
        if self.connected and self.db is not None:
            try:
                self.db.cameras.delete_many({})
                self.db.alerts.delete_many({})
                self.db.behaviour_events.delete_many({})
                self.db.detections.delete_many({})
                logger.info("Cleared all collections in MongoDB.")
            except Exception as e:
                logger.error(f"MongoDB clear error: {e}")
        self._memory_cameras = []
        self._memory_alerts = []
        self._memory_behaviour = []
        self._memory_detections = []

    def is_connected(self):
        return self.connected

    # ==========================================
    # CAMERAS CRUD
    # ==========================================
    def get_cameras(self):
        if self.connected:
            try:
                cams = list(self.db.cameras.find({}, {"_id": 0}))
                return cams
            except Exception as e:
                logger.error(f"MongoDB read error in get_cameras: {e}")
        return self._memory_cameras

    def get_camera(self, camera_id):
        if self.connected:
            try:
                cam = self.db.cameras.find_one({"camera_id": camera_id}, {"_id": 0})
                if cam:
                    return cam
            except Exception as e:
                logger.error(f"MongoDB read error in get_camera: {e}")
        return next((c for c in self._memory_cameras if c["camera_id"] == camera_id), None)

    def add_camera(self, camera_data):
        camera_id = camera_data.get("camera_id")
        if not camera_id:
            cams = self.get_cameras()
            camera_id = f"CCTV-{len(cams) + 1:02d}"
            camera_data["camera_id"] = camera_id

        camera_data.setdefault("status", "ONLINE")
        camera_data.setdefault("enabled", True)
        camera_data.setdefault("resolution", "1920x1080")
        camera_data.setdefault("fps_limit", 30)
        camera_data.setdefault("people_count", 0)
        camera_data.setdefault("density", "NORMAL")
        camera_data.setdefault("risk_level", "LOW")
        camera_data.setdefault("risk_score", 0)
        camera_data.setdefault("latest_event", "Node Registered")
        camera_data.setdefault("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        camera_data.setdefault("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

        if self.connected:
            try:
                # Remove _id if passed
                camera_data.pop("_id", None)
                self.db.cameras.insert_one(camera_data.copy())
            except Exception as e:
                logger.error(f"MongoDB write error in add_camera: {e}")
        
        # Keep memory copy in sync
        self._memory_cameras.append(camera_data)
        return camera_data

    def update_camera(self, camera_id, update_data):
        update_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        update_data.pop("_id", None)

        if self.connected:
            try:
                self.db.cameras.update_one({"camera_id": camera_id}, {"$set": update_data})
            except Exception as e:
                logger.error(f"MongoDB update error in update_camera: {e}")

        for cam in self._memory_cameras:
            if cam["camera_id"] == camera_id:
                cam.update(update_data)
                return cam
        return self.get_camera(camera_id)

    def delete_camera(self, camera_id):
        deleted = False
        if self.connected:
            try:
                res = self.db.cameras.delete_one({"camera_id": camera_id})
                deleted = res.deleted_count > 0
            except Exception as e:
                logger.error(f"MongoDB delete error in delete_camera: {e}")

        initial_len = len(self._memory_cameras)
        self._memory_cameras = [c for c in self._memory_cameras if c["camera_id"] != camera_id]
        if len(self._memory_cameras) < initial_len:
            deleted = True
        return deleted

    # ==========================================
    # ALERTS CRUD
    # ==========================================
    def get_alerts(self, camera_id=None, severity=None, status=None, limit=100):
        query = {}
        if camera_id:
            query["camera_id"] = camera_id
        if severity:
            query["severity"] = severity
        if status:
            query["status"] = status

        if self.connected:
            try:
                alerts = list(self.db.alerts.find(query, {"_id": 0}).sort("timestamp", DESCENDING).limit(limit))
                return alerts
            except Exception as e:
                logger.error(f"MongoDB read error in get_alerts: {e}")

        filtered = self._memory_alerts
        if camera_id:
            filtered = [a for a in filtered if a["camera_id"] == camera_id]
        if severity:
            filtered = [a for a in filtered if a["severity"] == severity]
        if status:
            filtered = [a for a in filtered if a["status"] == status]
        return filtered[:limit]

    def add_alert(self, alert_data):
        if not alert_data.get("event_id"):
            alert_data["event_id"] = f"EVT-{int(datetime.now().timestamp() * 1000) % 10000:04d}"
        alert_data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        alert_data.setdefault("status", "NEW")
        alert_data.setdefault("acknowledged_by", None)
        alert_data.setdefault("resolved_at", None)

        if self.connected:
            try:
                alert_data.pop("_id", None)
                self.db.alerts.insert_one(alert_data.copy())
            except Exception as e:
                logger.error(f"MongoDB insert error in add_alert: {e}")

        self._memory_alerts.insert(0, alert_data)
        return alert_data

    def update_alert_status(self, event_id, status, officer_name=None):
        update_doc = {"status": status}
        if officer_name:
            update_doc["acknowledged_by"] = officer_name
        if status in ("RESOLVED", "FALSE_POSITIVE"):
            update_doc["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if self.connected:
            try:
                self.db.alerts.update_one({"event_id": event_id}, {"$set": update_doc})
            except Exception as e:
                logger.error(f"MongoDB update error in update_alert_status: {e}")

        for alert in self._memory_alerts:
            if alert["event_id"] == event_id:
                alert.update(update_doc)
                return alert
        return None

    # ==========================================
    # BEHAVIOUR EVENTS & DETECTIONS LOGGING
    # ==========================================
    def log_behaviour_event(self, event_data):
        event_data.setdefault("start_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if self.connected:
            try:
                event_data.pop("_id", None)
                self.db.behaviour_events.insert_one(event_data.copy())
            except Exception as e:
                logger.error(f"MongoDB log behaviour error: {e}")
        self._memory_behaviour.append(event_data)
        return event_data

    def log_detection(self, detection_data):
        detection_data.setdefault("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        if self.connected:
            try:
                detection_data.pop("_id", None)
                self.db.detections.insert_one(detection_data.copy())
            except Exception as e:
                logger.error(f"MongoDB log detection error: {e}")
        self._memory_detections.append(detection_data)
        return detection_data

# Singleton accessor instance
db_manager = DatabaseManager()
