from flask import Blueprint, request, jsonify
from config import Database
from utils.auth import hash_password, verify_password, generate_token
from datetime import datetime

# blueprint for authentication routes
auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """
    Login endpoint
    
    Request Body:
        {
            "email": "receptionist@hospital.com",
            "password": "password123"
        }
    
    Response:
        {
            "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            "user": {
                "id": "1",
                "email": "receptionist@hospital.com",
                "name": "Jane Doe",
                "role": "receptionist"
            }
        }
    """
    try:
        # Get request data
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email')
        password = data.get('password')
        
        # Validate input
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Query database for user
        query = """
            SELECT 
                user_id,
                username,
                password_hash,
                role,
                is_active
            FROM users
            WHERE username = %s
            LIMIT 1
        """
        
        user = Database.execute_query(query, (email,), fetch_one=True)
        
        if not user:
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Check if user is active
        if not user['is_active']:
            return jsonify({'error': 'Account is disabled'}), 401
        
        # Verify password
        if not verify_password(password, user['password_hash']):
            return jsonify({'error': 'Invalid credentials'}), 401
        
        # Update last login timestamp
        update_query = """
            UPDATE users
            SET last_login = %s
            WHERE user_id = %s
        """
        Database.execute_query(
            update_query, 
            (datetime.now(), user['user_id']), 
            commit=True
        )
        
        # Generate JWT token
        token_data = {
            'user_id': user['user_id'],
            'username': user['username'],
            'role': user['role']
        }
        
        token = generate_token(token_data)
        
        # Return success response
        return jsonify({
            'token': token,
            'user': {
                'id': str(user['user_id']),
                'email': user['username'],
                'name': user['username'],
                'role': user['role']
            }
        }), 200
        
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'error': 'An error occurred during login'}), 500


@auth_bp.route('/api/auth/verify', methods=['GET'])
def verify_token():
    """
    Verify if the current token is valid
    
    Headers:
        Authorization: Bearer <token>
    
    Response:
        {
            "valid": true,
            "user": {
                "id": "1",
                "username": "receptionist",
                "role": "receptionist"
            }
        }
    """
    try:
        from utils.auth import decode_token
        
        # Get token from header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return jsonify({'valid': False, 'error': 'No token provided'}), 401
        
        try:
            token = auth_header.split(' ')[1]
        except IndexError:
            return jsonify({'valid': False, 'error': 'Invalid token format'}), 401
        
        # Decode token
        user_data = decode_token(token)
        
        if not user_data:
            return jsonify({'valid': False, 'error': 'Invalid or expired token'}), 401
        
        return jsonify({
            'valid': True,
            'user': {
                'id': str(user_data['user_id']),
                'username': user_data['username'],
                'role': user_data['role']
            }
        }), 200
        
    except Exception as e:
        print(f"Token verification error: {e}")
        return jsonify({'valid': False, 'error': 'Verification failed'}), 500