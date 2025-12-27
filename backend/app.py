"""Flask application factory."""
import logging
import os
from flask import Flask, send_from_directory, request
from flask_cors import CORS
from flask_compress import Compress
import re

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
        # Clean the path
        clean_path = path.strip('/')
        
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
            
        # Handle Public Profile OG Tags for social sharing
        # Support both @username and u/username
        username = None
        if clean_path.startswith('@'):
            username = clean_path[1:]
        elif clean_path.startswith('u/'):
            username = clean_path[2:]
            
        if username:
            try:
                from routes.public import get_user_profile_by_username
                profile = get_user_profile_by_username(username)
                
                if profile:
                    index_path = os.path.join(app.static_folder, 'index.html')
                    if os.path.exists(index_path):
                        with open(index_path, 'r') as f:
                            html = f.read()
                        
                        display_name = profile.get('full_name') or username
                        count = profile.get('bookmark_count') or 0
                        title = f"{display_name}'s Reads on Markly"
                        description = f"Discover {count} interesting finds curated by {display_name}."
                        image = profile.get('avatar_url') or profile.get('picture')
                        if not image:
                            # Use a nice UI Avatar as fallback for OG image
                            image = f"https://ui-avatars.com/api/?name={display_name}&background=6366f1&color=fff&size=512"
                        
                        # Use the requested path format in the URL tag
                        if clean_path.startswith('@'):
                            url = f"https://markly.azurewebsites.net/@{username}"
                        else:
                            url = f"https://markly.azurewebsites.net/u/{username}"
                        
                        # Strip existing generic meta tags to avoid confusion for crawlers
                        tags_to_strip = [
                            r'<title>.*?</title>',
                            r'<meta\s+[^>]*?name="description"[^>]*?>',
                            r'<meta\s+[^>]*?property="og:title"[^>]*?>',
                            r'<meta\s+[^>]*?property="og:description"[^>]*?>',
                            r'<meta\s+[^>]*?property="og:image"[^>]*?>',
                            r'<meta\s+[^>]*?property="og:url"[^>]*?>',
                            r'<meta\s+[^>]*?property="og:site_name"[^>]*?>',
                            r'<meta\s+[^>]*?name="twitter:title"[^>]*?>',
                            r'<meta\s+[^>]*?name="twitter:description"[^>]*?>',
                            r'<meta\s+[^>]*?name="twitter:image"[^>]*?>',
                            r'<meta\s+[^>]*?name="twitter:card"[^>]*?>'
                        ]
                        
                        for tag_re in tags_to_strip:
                            html = re.sub(tag_re, '', html, flags=re.IGNORECASE | re.DOTALL)

                        # Prepare fresh, personalized OG tags
                        # Ensure we have the minimum required tags: og:title, og:type, og:image, og:url
                        og_tags = f'''
    <title>{title}</title>
    <meta name="description" content="{description}">
    <meta property="og:site_name" content="Markly">
    <meta property="og:title" content="{title}">
    <meta property="og:description" content="{description}">
    <meta property="og:image" content="{image}">
    <meta property="og:url" content="{url}">
    <meta property="og:type" content="profile">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{title}">
    <meta name="twitter:description" content="{description}">
    <meta name="twitter:image" content="{image}">
'''
                        # Inject into head - find the end of <head> or start of it
                        # Injecting right after <head> is safest
                        html = re.sub(r'(<head[^>]*>)', r'\1' + og_tags, html, flags=re.IGNORECASE)
                        return html
            except Exception as e:
                app.logger.error(f"Error injecting OG tags for {username}: {e}")

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
