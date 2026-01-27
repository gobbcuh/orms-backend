import os
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config, Database
from routes.auth import auth_bp
from routes.patients import patients_bp
from routes.billing import billing_bp
from routes.reference import reference_bp


def create_app():
    """Application factory pattern"""
    
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # enabling CORS for frontend (port 8080)
    CORS(app, resources={
        r"/api/*": {
            "origins": Config.CORS_ORIGINS,
            "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"]
        }
    })
    
    # database connection pool
    try:
        Database.initialize_pool()
        print("- Database connection pool initialized")
    except Exception as e:
        print(f"- Failed to initialize database: {e}")
        raise
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(billing_bp)
    app.register_blueprint(reference_bp)
    
    @app.route('/api/health', methods=['GET'])
    def health_check():
        """Simple health check endpoint"""
        try:
            # testing db connection
            result = Database.execute_query("SELECT 1 as test")
            db_status = "connected" if result else "disconnected"
        except:
            db_status = "error"
        
        return jsonify({
            'status': 'running',
            'database': db_status,
            'message': 'ORMS Backend API is running'
        }), 200
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app


if __name__ == '__main__':
    app = create_app()
    
    print("\n" + "=" * 70)
    print("ORMS Backend API Server")
    print("=" * 70)
    print(f"- Running on: http://localhost:{Config.PORT}")
    print(f"- CORS enabled for: {', '.join(Config.CORS_ORIGINS)}")
    print(f"- Environment: {os.getenv('FLASK_ENV', 'production')}")
    print("=" * 70)
    print("\nStarting server...\n")
    
    app.run(
        host='0.0.0.0',
        port=Config.PORT,
        debug=Config.DEBUG
    )