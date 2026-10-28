from flask import Blueprint, request, jsonify, session, render_template, redirect, url_for

auth_bp = Blueprint("auth", __name__)

# Default demo credentials
DEFAULT_USER = {
    "username": "admin",
    "password": "password123",
    "role": "Security Supervisor",
    "name": "Commander Alex Vance"
}

@auth_bp.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        data = request.form
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()
        
        if (username == DEFAULT_USER["username"] and password == DEFAULT_USER["password"]) or (username == "admin" and password == "admin"):
            session["logged_in"] = True
            session["username"] = DEFAULT_USER["username"]
            session["role"] = DEFAULT_USER["role"]
            session["name"] = DEFAULT_USER["name"]
            return redirect(url_for("dashboard_page"))
        else:
            return render_template("login.html", error="Invalid Security Clearance ID or Password.")
            
    if session.get("logged_in"):
        return redirect(url_for("dashboard_page"))
        
    return render_template("login.html")

@auth_bp.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()

    if (username == DEFAULT_USER["username"] and password == DEFAULT_USER["password"]) or (username == "admin" and password == "admin"):
        session["logged_in"] = True
        session["username"] = DEFAULT_USER["username"]
        session["role"] = DEFAULT_USER["role"]
        session["name"] = DEFAULT_USER["name"]
        return jsonify({
            "status": "success",
            "message": "Authentication successful",
            "user": {
                "username": session["username"],
                "role": session["role"],
                "name": session["name"]
            }
        })
    
    return jsonify({"status": "error", "message": "Invalid security credentials"}), 401

@auth_bp.route("/api/auth/logout", methods=["POST", "GET"])
def api_logout():
    session.clear()
    if request.method == "GET":
        return redirect(url_for("auth.login_page"))
    return jsonify({"status": "success", "message": "Logged out successfully"})
