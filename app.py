import os
from flask import Flask, render_template, redirect, url_for, jsonify
from config import Config
from database.mongo import db_manager
from routes.auth import auth_bp
from routes.cameras import cameras_bp
from routes.alerts import alerts_bp
from routes.analytics import analytics_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(cameras_bp)
    app.register_blueprint(alerts_bp)
    app.register_blueprint(analytics_bp)

    @app.route("/")
    def index():
        return redirect(url_for("dashboard_page"))

    @app.route("/dashboard")
    def dashboard_page():
        # Fetch live camera matrix and active alerts from MongoDB / Data Layer
        cameras = db_manager.get_cameras()
        alerts = db_manager.get_alerts(limit=5)
        
        online_count = sum(1 for c in cameras if c.get("status") == "ONLINE")
        total_people = sum(c.get("people_count", 0) for c in cameras)
        active_threats = sum(1 for a in alerts if a.get("status") in ("NEW", "ACKNOWLEDGED"))
        highest_score = max((c.get("risk_score", 0) for c in cameras), default=0)
        
        if highest_score >= 81:
            highest_level = "CRITICAL"
        elif highest_score >= 61:
            highest_level = "HIGH"
        elif highest_score >= 31:
            highest_level = "MEDIUM"
        else:
            highest_level = "LOW"

        highest_cam = next((c for c in cameras if c.get("risk_score") == highest_score), None)
        highest_cam_label = f"{highest_cam.get('camera_id')} ({highest_cam.get('name')})" if highest_cam else "All Sectors Normal"

        return render_template(
            "dashboard.html",
            cameras=cameras,
            alerts=alerts,
            online_count=online_count,
            total_cameras=len(cameras),
            total_people=total_people,
            active_threats=active_threats,
            highest_score=highest_score,
            highest_level=highest_level,
            highest_cam_label=highest_cam_label,
            db_connected=db_manager.is_connected()
        )

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        from flask import send_from_directory
        uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
        return send_from_directory(uploads_dir, filename)

    @app.route("/api/health", methods=["GET"])
    def health_check():
        return jsonify({
            "status": "healthy",
            "service": "CROWDGUARD AI Core Engine",
            "version": "1.0.0-Phase2",
            "mode": "DEMO_MODE" if Config.DEMO_MODE else "PRODUCTION",
            "database": {
                "type": "MongoDB",
                "uri": Config.MONGO_URI,
                "db_name": Config.MONGO_DB_NAME,
                "connected": db_manager.is_connected(),
                "status": "ONLINE" if db_manager.is_connected() else "OFFLINE (In-Memory Fallback Active)"
            },
            "active_modules": [
                "Control Room Web UI",
                "MongoDB Persistence Layer",
                "Camera CRUD Pipeline",
                "Alert Storage & Deduplication Engine",
                "RESTful Threat API"
            ]
        })

    @app.errorhandler(404)
    def page_not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        return jsonify({
            "status": "error",
            "message": "Internal Surveillance Engine Error",
            "details": str(e)
        }), 500

    return app

app = create_app()

if __name__ == "__main__":
    print("=" * 65)
    print(" CROWDGUARD AI: Surveillance & Threat Analysis System")
    print(f" Phase 2: MongoDB Persistence Layer Active")
    print(f" Web Server: http://{Config.HOST}:{Config.PORT}")
    print(f" Database Status: {'CONNECTED' if db_manager.is_connected() else 'OFFLINE (In-Memory Fallback Active)'}")
    print(f" Mode: {'DEMO MODE (Active)' if Config.DEMO_MODE else 'STANDARD'}")
    print("=" * 65)
    app.run(host=Config.HOST, port=Config.PORT, debug=False, threaded=True)
