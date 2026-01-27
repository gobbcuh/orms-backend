import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import Config
import hashlib


# PASSWORD HASHING

def hash_password(password):
    """Hash a password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password, hashed_password):
    """Verify a password against its hash"""
    return hash_password(plain_password) == hashed_password


# ============================================================================
# JWT TOKEN GENERATION

def generate_token(user_data):
    """
    Generate a JWT token for authenticated user
    
    Args:
        user_data: Dictionary containing user info (user_id, username, role)
    
    Returns:
        JWT token string
    """
    payload = {
        'user_id': user_data['user_id'],
        'username': user_data['username'],
        'role': user_data['role'],
        'exp': datetime.utcnow() + timedelta(hours=Config.JWT_EXPIRATION_HOURS),
        'iat': datetime.utcnow()
    }
    
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm='HS256')
    return token


def decode_token(token):
    """
    Decode and verify a JWT token
    
    Args:
        token: JWT token string
    
    Returns:
        Decoded payload or None if invalid
    """
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None # token has expired
    except jwt.InvalidTokenError:
        return None  # invalid token


# ============================================================================
# AUTHENTICATION DECORATOR

def token_required(f):
    """
    Decorator to protect routes that require authentication
    
    Usage:
        @app.route('/api/patients')
        @token_required
        def get_patients(current_user):
            # current_user contains decoded token data
            pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # checking if token is in the authorization header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Authentication token is missing'}), 401
        
        current_user = decode_token(token)
        
        if not current_user:
            return jsonify({'error': 'Invalid or expired token'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated


# ============================================================================
# OPTIONAL: ROLE-BASED ACCESS CONTROL

def role_required(allowed_roles):
    """
    Decorator to restrict access based on user role
    
    Args:
        allowed_roles: List of allowed roles (e.g., ['admin', 'receptionist'])
    
    Usage:
        @app.route('/api/admin/users')
        @role_required(['admin'])
        def get_users(current_user):
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated(current_user, *args, **kwargs):
            if current_user['role'] not in allowed_roles:
                return jsonify({'error': 'Insufficient permissions'}), 403
            
            return f(current_user, *args, **kwargs)
        
        return decorated
    return decorator