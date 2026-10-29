"""
app.py — Main Flask application entry point
Multimodal Attendance & Engagement Agent
"""

import logging
import sys
from pathlib import Path

from flask import Flask, render_template, redirect, url_for, session, request, jsonify

from config import Config
from models.database import init_db

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(Config.LOG_FILE, encoding="utf-8"),
    ],
)
logger = logging.getLogger("app")


def create_app() -> Flask:
    Config.ensure_dirs()
    init_db()

    app = Flask(
        __name__,
        template_folder="frontend/templates",
        static_folder="frontend/static",
    )
    app.secret_key = Config.SECRET_KEY
    app.config["MAX_CONTENT_LENGTH"] = Config.MAX_CONTENT_LENGTH

    # ── Register blueprints ───────────────────────────────────────────────
    from routes.session_routes import bp as session_bp
    from routes.attendance_routes import bp as attendance_bp
    from routes.engagement_routes import bp as engagement_bp
    from routes.recommendation_routes import bp as recommendation_bp
    from routes.report_routes import bp as report_bp

    app.register_blueprint(session_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(engagement_bp)
    app.register_blueprint(recommendation_bp)
    app.register_blueprint(report_bp)

    # Health endpoint at root /api/health
    @app.route("/api/health")
    def health():
        from routes.report_routes import health as _h
        return _h()

    # ── Frontend page routes ──────────────────────────────────────────────
    @app.route("/")
    def index():
        return redirect(url_for("dashboard"))

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/sessions")
    def sessions_page():
        return render_template("sessions.html")

    @app.route("/sessions/<session_id>/attendance")
    def attendance_page(session_id):
        return render_template("attendance.html", session_id=session_id)

    @app.route("/sessions/<session_id>/engagement")
    def engagement_page(session_id):
        return render_template("engagement.html", session_id=session_id)

    @app.route("/sessions/<session_id>/recommendations")
    def recommendations_page(session_id):
        return render_template("recommendations.html", session_id=session_id)

    @app.route("/sessions/<session_id>/report")
    def report_page(session_id):
        return render_template("reports.html", session_id=session_id)

    @app.route("/settings")
    def settings_page():
        return render_template("settings.html")

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Not found"}), 404
        return render_template("base.html"), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"error": "File too large"}), 413

    @app.errorhandler(500)
    def server_error(e):
        logger.exception("Internal server error")
        if request.path.startswith("/api/"):
            return jsonify({"error": "Internal server error"}), 500
        return render_template("base.html"), 500

    logger.info("Multimodal Attendance Agent started (DEBUG=%s)", Config.DEBUG)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG, use_reloader=False)
