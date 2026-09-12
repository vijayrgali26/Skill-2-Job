import os

from flask import Flask, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

from config import config_by_name

db = SQLAlchemy()
migrate = Migrate()

# Path to the React production build output (Vite uses ``dist/``)
_FRONTEND_DIST = os.path.join(
    os.path.abspath(os.path.dirname(__file__)), "..", "..", "frontend", "dist"
)


def create_app(config_name='default'):
    """Flask application factory.

    Args:
        config_name: Configuration to use ('development', 'testing', 'production', or 'default').

    Returns:
        Configured Flask application instance.
    """
    # Resolve the frontend dist directory (may not exist in testing)
    frontend_dist = os.path.normpath(_FRONTEND_DIST)
    has_frontend = os.path.isdir(frontend_dist)

    app = Flask(
        __name__,
        static_folder=frontend_dist if has_frontend else None,
        static_url_path="/" if has_frontend else None,
    )
    app.config.from_object(config_by_name[config_name])

    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder and not os.path.isabs(upload_folder):
        app.config['UPLOAD_FOLDER'] = os.path.normpath(
            os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', upload_folder)
        )

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Ensure upload folder exists when the application starts
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder:
        os.makedirs(upload_folder, exist_ok=True)

    # CORS — allow Vercel frontend in production, all origins in dev
    allowed_origins = os.environ.get(
        'CORS_ORIGINS',
        '*'  # dev default; set CORS_ORIGINS=https://your-app.vercel.app in production
    )
    CORS(app, resources={r"/api/*": {"origins": allowed_origins}})

    # Import models so SQLAlchemy registers them for migrations and create_all
    from app import models  # noqa: F401

    # Register blueprints
    from app.routes.auth_routes import auth_bp
    app.register_blueprint(auth_bp)

    from app.routes.profile_routes import profile_bp
    app.register_blueprint(profile_bp)

    from app.routes.skill_routes import skill_bp
    app.register_blueprint(skill_bp)

    from app.routes.job_routes import job_bp
    app.register_blueprint(job_bp)

    from app.routes.resume_routes import resume_bp
    app.register_blueprint(resume_bp)

    from app.routes.admin_routes import admin_bp
    app.register_blueprint(admin_bp)

    from app.routes.dashboard_routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    from app.routes.interview_routes import interview_bp
    app.register_blueprint(interview_bp)

    from app.routes.notification_routes import notification_bp
    app.register_blueprint(notification_bp)

    from app.routes.placement_routes import placement_bp
    app.register_blueprint(placement_bp)

    from app.routes.stats_routes import stats_bp
    app.register_blueprint(stats_bp)

    # Register input sanitization before_request hook
    from app.utils.sanitizer import register_sanitizer
    register_sanitizer(app)

    # Register global error handlers
    from app.utils.error_handlers import register_error_handlers
    register_error_handlers(app)

    # ------------------------------------------------------------------
    # Dev mode: redirect root and non-API paths to Vite dev server
    # Production: serve the built React SPA from frontend/dist
    # ------------------------------------------------------------------
    if has_frontend:
        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def serve_react(path):
            full_path = os.path.join(frontend_dist, path)
            if path and os.path.isfile(full_path):
                return send_from_directory(frontend_dist, path)
            return send_from_directory(frontend_dist, "index.html")
    else:
        # Development: no built frontend — redirect browser to Vite dev server
        from flask import redirect as flask_redirect, request as flask_request

        @app.route("/", defaults={"path": ""})
        @app.route("/<path:path>")
        def dev_redirect(path):
            # Don't intercept API calls
            if flask_request.path.startswith("/api/"):
                from flask import abort
                abort(404)
            frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
            return flask_redirect(frontend_url + "/" + path, code=302)

    return app
