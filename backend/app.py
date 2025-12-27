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

    # --- Public Profile Injection Logic ---
    def serve_with_injection(username, full_path):
        """Helper to serve index.html with injected OG tags."""
        clean_username = username.strip('@').strip('/')
        index_path = os.path.join(app.static_folder, 'index.html')
        
        if not os.path.exists(index_path):
            return "App is building, please refresh...", 503

        with open(index_path, 'r') as f:
            html = f.read()

        # Try to get profile data
        profile = None
        try:
            from routes.public import get_user_profile_by_username
            profile = get_user_profile_by_username(clean_username)
        except Exception as e:
            app.logger.error(f"Error looking up profile for {clean_username}: {e}")

        # Fallback values if profile lookup fails
        display_name = clean_username
        first_name = clean_username
        count = 0
        image = f"https://ui-avatars.com/api/?name={clean_username}&background=6366f1&color=fff&size=512"
        
        if profile:
            full_name = profile.get('full_name') or clean_username
            display_name = full_name
            # Extract first name for a friendlier title
            first_name = full_name.split()[0] if full_name else clean_username
            count = profile.get('bookmark_count') or 0
            image = profile.get('avatar_url') or profile.get('picture') or image

        description = f"Discover {count} interesting finds curated by {display_name} on Markly."
        title = f"{display_name} - Markly"
        # Ensure URL is absolute and matches the requested format
        base_url = "https://markly.azurewebsites.net"
        # If it was a /u/ route, keep it as /u/ in the og:url
        url = f"{base_url}{full_path}"

        # Strip existing generic meta tags to avoid confusion for crawlers
        # We use a broad regex to catch many variations
        tags_to_strip = [
            r'<title>.*?</title>',
            r'<meta\s+[^>]*?name="description"[^>]*?>',
            r'<meta\s+[^>]*?property="og:title"[^>]*?>',
            r'<meta\s+[^>]*?property="og:description"[^>]*?>',
            r'<meta\s+[^>]*?property="og:image"[^>]*?>',
            r'<meta\s+[^>]*?property="og:url"[^>]*?>',
            r'<meta\s+[^>]*?property="og:site_name"[^>]*?>',
            r'<meta\s+[^>]*?property="og:type"[^>]*?>',
            r'<meta\s+[^>]*?name="twitter:title"[^>]*?>',
            r'<meta\s+[^>]*?name="twitter:description"[^>]*?>',
            r'<meta\s+[^>]*?name="twitter:image"[^>]*?>',
            r'<meta\s+[^>]*?name="twitter:card"[^>]*?>'
        ]
        
        for tag_re in tags_to_strip:
            html = re.sub(tag_re, '', html, flags=re.IGNORECASE | re.DOTALL)

        # Prepare fresh, personalized OG tags
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
        # Inject right after <head>
        html = re.sub(r'(<head[^>]*>)', r'\1' + og_tags, html, flags=re.IGNORECASE)
        return html

    # Canonical profile route: /@username
    @app.route('/@<username>')
    def profile_serve(username):
        return serve_with_injection(username, f"/@{username}")

    # Redirect /u/username to /@username for backwards compatibility
    @app.route('/u/<username>')
    def profile_redirect(username):
        from flask import redirect
        return redirect(f"/@{username}", code=301)

    # SPA Routing: Serve index.html for all non-API paths
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def serve(path):
        # Clean the path
        clean_path = path.strip('/')
        
        if path != "" and os.path.exists(os.path.join(app.static_folder, path)):
            return send_from_directory(app.static_folder, path)
            
        # Handle Public Profile OG Tags for social sharing
        # This handles cases not caught by explicit u/ and @ routes
        if clean_path.startswith('@'):
            return serve_with_injection(clean_path[1:], request.path)
        elif clean_path.startswith('u/'):
            return serve_with_injection(clean_path[2:], request.path)

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
