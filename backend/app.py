"""Flask application factory."""
import logging
import os
from flask import Flask, send_from_directory, request
from flask_cors import CORS
from flask_compress import Compress

from config import Config


def create_app():
    """Create and configure the Flask application."""
    # Create app, pointing to the 'static' folder for static assets (JS/CSS)
    # The Dockerfile copies frontend/dist to ./static in the container
    static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
    app = Flask(__name__, static_folder=static_dir, static_url_path='/')
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
    from routes.public import public_bp
    
    app.register_blueprint(bookmarks_bp, url_prefix="/api/bookmarks")
    app.register_blueprint(search_bp, url_prefix="/api/search")
    app.register_blueprint(stats_bp, url_prefix="/api/stats")
    app.register_blueprint(public_bp, url_prefix="/api/public")  # Public profile routes
    
    # Health check endpoint
    @app.route("/api/health")
    def health():
        return {"status": "healthy", "service": "markly-api"}

    # SPA Routing: Serve index.html for all non-API paths
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
            
        # Handle Public Profile OG Tags for social sharing
        if path.startswith('@'):
            username = path[1:]
            try:
                from routes.public import get_user_profile_by_username
                profile = get_user_profile_by_username(username)
                
                if profile:
                    index_path = os.path.join(app.static_folder, 'index.html')
                    if os.path.exists(index_path):
                        with open(index_path, 'r') as f:
                            html = f.read()
                        
                        display_name = profile.get('full_name') or username
                        title = f"{display_name}'s Reads on Markly"
                        description = f"Explore curated links and interesting finds from {display_name}."
                        image = profile.get('avatar_url') or "https://markly.azurewebsites.net/og-image.png"
                        url = f"https://markly.azurewebsites.net/@{username}"
                        
                        # Prepare OG tags
                        og_tags = f'''
    <!-- Dynamic OG Tags -->
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{image}">
    <meta property="og:url" content="{url}">
    <meta property="og:type" content="website">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="{image}">
'''
                        # Inject into head (replace existing title if possible or just append)
                        html = html.replace('<head>', f'<head>{og_tags}')
                        return html
            except Exception as e:
                app.logger.error(f"Error injecting OG tags: {e}")

        return send_from_directory(app.static_folder, 'index.html')

    @app.errorhandler(404)
    def not_found(e):
        if not request.path.startswith('/api/'):
            return send_from_directory(app.static_folder, 'index.html')
        return e
    
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5000)
