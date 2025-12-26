"""Flask application factory."""
import logging
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_compress import Compress

from config import Config


def create_app():
    """Create and configure the Flask application."""
    # Create app, pointing to the 'static' folder for static assets (JS/CSS)
    # The Dockerfile copies frontend/dist to ./static in the container
    app = Flask(__name__, static_folder='static', static_url_path='/')
    app.config.from_object(Config)
    
    # Silence noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('hpack').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    # Enable CORS for frontend
    CORS(app, origins=["http://localhost:5173", "http://localhost:3000"], 
         supports_credentials=True)
    
    # Enable Gzip compression
    Compress(app)
    
    # Validate configuration on startup
    try:
        Config.validate()
    except ValueError as e:
        app.logger.warning(f"Configuration warning: {e}")
    
    # Register blueprints
    from routes.bookmarks import bookmarks_bp
    from routes.search import search_bp
    from routes.stats import stats_bp
    
    app.register_blueprint(bookmarks_bp, url_prefix="/api/bookmarks")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(stats_bp, url_prefix="/api/stats")
    
    # Health check endpoint
    @app.route("/api/health")
    def health():
        return {"status": "healthy", "service": "markly-api"}

    # Serve React Frontend in Production
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(app.static_folder + '/' + path):
            return send_from_directory(app.static_folder, path)
        else:
            return send_from_directory(app.static_folder, 'index.html')
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
