from flask import Blueprint, jsonify
from config import Database
from utils.auth import token_required
from utils.formatters import format_service_response

reference_bp = Blueprint('reference', __name__)

@reference_bp.route('/api/departments', methods=['GET'])
@token_required
def get_departments(current_user):
    """Get list of all departments"""
    try:
        query = """
            SELECT department_id, name, code, description
            FROM departments
            ORDER BY name
        """
        results = Database.execute_query(query)
        return jsonify(results), 200
    except Exception as e:
        print(f"Error getting departments: {e}")
        return jsonify({'error': 'Failed to retrieve departments'}), 500


@reference_bp.route('/api/doctors/by-department/<department_id>', methods=['GET'])
@token_required
def get_doctors_by_department(current_user, department_id):
    """Get doctors in a specific department"""
    try:
        query = """
            SELECT 
                doctor_id,
                CONCAT(first_name, ' ', last_name) as full_name
            FROM doctors
            WHERE department_id = %s
            ORDER BY first_name, last_name
        """
        results = Database.execute_query(query, (department_id,))
        doctors = [row['full_name'] for row in results]
        return jsonify(doctors), 200
    except Exception as e:
        print(f"Error getting doctors by department: {e}")
        return jsonify({'error': 'Failed to retrieve doctors'}), 500
    

@reference_bp.route('/api/doctors', methods=['GET'])
@token_required
def get_doctors(current_user):
    """Get list of all doctors with department info"""
    try:
        query = """
            SELECT 
                d.doctor_id,
                CONCAT(d.first_name, ' ', d.last_name) as full_name,
                dept.name as department_name,
                dept.department_id
            FROM doctors d
            LEFT JOIN departments dept ON d.department_id = dept.department_id
            ORDER BY dept.name, d.first_name, d.last_name
        """
        results = Database.execute_query(query)
        return jsonify(results), 200
    except Exception as e:
        print(f"Error getting doctors: {e}")
        return jsonify({'error': 'Failed to retrieve doctors'}), 500


@reference_bp.route('/api/services', methods=['GET'])
@token_required
def get_services(current_user):
    """
    Get list of all medical services
    
    Response:
        Array of service objects
        Example: [
            {"id": "consultation", "name": "Consultation Fee", "price": 150.00},
            {"id": "bloodtest", "name": "Blood Test", "price": 75.00}
        ]
    """
    try:
        query = """
            SELECT service_id, name, price
            FROM services
            WHERE is_active = 1
            ORDER BY name
        """
        
        results = Database.execute_query(query)
        
        # format services
        services = [format_service_response(row) for row in results]
        
        return jsonify(services), 200
        
    except Exception as e:
        print(f"Error getting services: {e}")
        return jsonify({'error': 'Failed to retrieve services'}), 500


@reference_bp.route('/api/payment-methods', methods=['GET'])
@token_required
def get_payment_methods(current_user):
    """
    Get list of all payment methods
    
    Response:
        Array of payment method name strings
        Example: ["Cash", "Credit Card", "Debit Card", "Insurance", "Bank Transfer"]
    """
    try:
        query = """
            SELECT name
            FROM payment_methods
            ORDER BY method_id
        """
        
        results = Database.execute_query(query)
        
        payment_methods = [row['name'] for row in results]
        
        return jsonify(payment_methods), 200
        
    except Exception as e:
        print(f"Error getting payment methods: {e}")
        return jsonify({'error': 'Failed to retrieve payment methods'}), 500