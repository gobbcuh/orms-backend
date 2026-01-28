import uuid
from flask import Blueprint, request, jsonify
from config import Database
from utils.auth import token_required
from utils.formatters import format_patient_response
from datetime import datetime

patients_bp = Blueprint('patients', __name__)


@patients_bp.route('/api/patients', methods=['GET'])
@token_required
def get_patients(current_user):
    """
    Get all patients with their latest visit information
    
    Query Parameters:
        status: Filter by visit status (waiting, checked-in, completed)
        doctor: Filter by assigned doctor
        search: Search by name or phone
    
    Response:
        Array of patient objects
    """
    try:
        # Get query parameters
        status_filter = request.args.get('status')
        doctor_filter = request.args.get('doctor')
        search_query = request.args.get('search')
        
        # base query - get patients with their most recent visit
        query = """
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.date_of_birth,
                p.phone,
                p.email,
                p.address,
                p.emergency_contact_name,
                p.emergency_contact_relationship,
                p.emergency_contact_phone,
                s.name as sex_name,
                gi.name as gender_identity_name,
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes,
                v.followup_date,
                vs.name as status_name,
                d.first_name as doctor_first_name,
                d.last_name as doctor_last_name
            FROM patients p
            LEFT JOIN sex s ON p.sex_id = s.sex_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id   -- ADD THIS
            LEFT JOIN (
                -- Get most recent visit for each patient
                SELECT v1.*
                FROM visits v1
                INNER JOIN (
                    SELECT patient_id, MAX(visit_datetime) as max_date
                    FROM visits
                    GROUP BY patient_id
                ) v2 ON v1.patient_id = v2.patient_id 
                    AND v1.visit_datetime = v2.max_date
            ) v ON p.patient_id = v.patient_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE 1=1
        """
        
        params = []
        
        # status filter
        if status_filter:
            query += " AND vs.name = %s"
            params.append(status_filter)
        
        # doctor filter
        if doctor_filter:
            query += " AND CONCAT(d.first_name, ' ', d.last_name) = %s"
            params.append(doctor_filter)
        
        # search filter
        if search_query:
            query += """ AND (
                CONCAT(p.first_name, ' ', p.last_name) LIKE %s
                OR p.phone LIKE %s
            )"""
            search_pattern = f"%{search_query}%"
            params.append(search_pattern)
            params.append(search_pattern)
        
        # Order by most recent visit first
        query += " ORDER BY v.visit_datetime DESC"
        
        # Execute query
        results = Database.execute_query(query, tuple(params) if params else None)
        
        # Format results for frontend
        patients = []
        for row in results:
            visit_data = None
            if row.get('visit_id'):
                visit_data = {
                    'visit_datetime': row['visit_datetime'],
                    'check_in_datetime': row['check_in_datetime'],
                    'status_name': row['status_name'],
                    'notes': row['notes'],
                    'followup_date': row['followup_date']
                }
            
            # Prepare doctor data
            doctor_data = None
            if row.get('doctor_first_name'):
                doctor_data = {
                    'first_name': row['doctor_first_name'],
                    'last_name': row['doctor_last_name']
                }
            
            # Format patient
            patient = format_patient_response(row, visit_data, doctor_data)
            patients.append(patient)
        
        return jsonify(patients), 200
        
    except Exception as e:
        print(f"Error getting patients: {e}")
        return jsonify({'error': 'Failed to retrieve patients'}), 500

@patients_bp.route('/api/patients', methods=['POST'])
@token_required
def create_patient(current_user):
    """
    Register new patient (creates patient + visit + invoice)
    
    Request Body:
        {
            "firstName": "John",
            "lastName": "Doe",
            "dateOfBirth": "1990-05-15",
            "gender": "male",
            "phone": "+63-917-123-4567",
            "email": "john@email.com",
            "address": "123 Street, City",
            "emergencyContact": "Jane Doe",
            "emergencyPhone": "+63-917-765-4321",
            "assignedDoctor": "Dr. Policarpio",
            "hasFollowUp": false,
            "followUpDate": null,
            "medicalNotes": "No known allergies"
        }
    
    Response:
        {
            "patient": { patient object },
            "invoice": { invoice object }
        }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate required fields
        required_fields = ['firstName', 'lastName', 'dateOfBirth', 'gender', 'phone']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'{field} is required'}), 400
        
        # Generate unique patient ID
        import uuid
        patient_id = f"PAT-{uuid.uuid4().hex[:6].upper()}"
        
        # Get sex_id from biological sex
        sex = data.get('sex', 'male').lower()
        sex_map = {'male': 1, 'female': 2}
        sex_id = sex_map.get(sex, 1)

        # Get gender_identity_id from gender identity
        gender = data.get('gender', 'male').lower()
        gender_map = {
            'male': 1,
            'female': 2,
            'non-binary': 3,
            'prefer not to say': 4,
            'other': 5
        }
        gender_identity_id = gender_map.get(gender, 4)  # Default to "Prefer not to say"
        
        # Step 1: Create patient record
        patient_query = """
            INSERT INTO patients (
                patient_id, first_name, last_name, date_of_birth, sex_id, gender_identity_id,
                phone, email, address, emergency_contact_name, emergency_contact_relationship,
                emergency_contact_phone, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        patient_params = (
            patient_id,
            data['firstName'],
            data['lastName'],
            data['dateOfBirth'],
            sex_id,
            gender_identity_id,
            data.get('phone', ''),
            data.get('email', ''),
            data.get('address', ''),
            data.get('emergencyContact', ''),
            data.get('emergencyContactRelationship', ''),
            data.get('emergencyPhone', '')
        )
        
        Database.execute_query(patient_query, patient_params, commit=True)
        
        # Step 2: Get doctor_id if assigned
        doctor_id = None
        if data.get('assignedDoctor'):
            doctor_name_parts = data['assignedDoctor'].split(' ', 1)
            if len(doctor_name_parts) == 2:
                doctor_query = """
                    SELECT doctor_id 
                    FROM doctors 
                    WHERE first_name = %s AND last_name = %s
                    LIMIT 1
                """
                doctor_result = Database.execute_query(
                    doctor_query, 
                    (doctor_name_parts[0], doctor_name_parts[1]), 
                    fetch_one=True
                )
                if doctor_result:
                    doctor_id = doctor_result['doctor_id']
        
        # Step 3: Create visit record
        visit_id = f"VIS-{uuid.uuid4().hex[:6].upper()}"
        visit_datetime = datetime.now()
        
        # Get followup date if provided
        followup_date = data.get('followUpDate') if data.get('hasFollowUp') else None
        
        visit_query = """
            INSERT INTO visits (
                visit_id, patient_id, doctor_id, visit_datetime,
                status_id, notes, followup_date, created_at, created_by_user_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
        """
        
        visit_params = (
            visit_id,
            patient_id,
            doctor_id,
            visit_datetime,
            1,  # status_id = 1 (waiting)
            data.get('medicalNotes', ''),
            followup_date,
            current_user['user_id']
        )
        
        Database.execute_query(visit_query, visit_params, commit=True)
        
        # Step 4: Create bill/invoice with consultation fee
        bill_id = f"BILL-{uuid.uuid4().hex[:6].upper()}"
        
        # Get consultation service price
        service_query = "SELECT price FROM services WHERE service_id = 'consultation' LIMIT 1"
        service_result = Database.execute_query(service_query, fetch_one=True)
        consultation_price = float(service_result['price']) if service_result else 150.00
        
        subtotal = consultation_price
        tax = subtotal * 0.1
        total = subtotal + tax
        
        bill_query = """
            INSERT INTO bills (
                bill_id, visit_id, patient_id, subtotal, tax, amount_total,
                status, billing_date, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, 'Pending', NOW(), NOW())
        """
        
        bill_params = (bill_id, visit_id, patient_id, subtotal, tax, total)
        Database.execute_query(bill_query, bill_params, commit=True)
        
        # Step 5: Add consultation service to bill_services
        service_id = f"SVC-{uuid.uuid4().hex[:6].upper()}"
        
        bill_service_query = """
            INSERT INTO bill_services (
                service_id, bill_id, service_name, amount, quantity
            ) VALUES (%s, %s, 'Consultation Fee', %s, 1)
        """
        
        Database.execute_query(
            bill_service_query, 
            (service_id, bill_id, consultation_price), 
            commit=True
        )
        
        # Step 6: Fetch and format the created patient
        fetch_query = """
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.date_of_birth,
                p.phone,
                p.email,
                p.address,
                p.emergency_contact_name,
                p.emergency_contact_relationship,
                p.emergency_contact_phone,
                s.name as sex_name,
                gi.name as gender_identity_name,
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes,
                v.followup_date,
                vs.name as status_name,
                d.first_name as doctor_first_name,
                d.last_name as doctor_last_name
            FROM patients p
            LEFT JOIN sex s ON p.sex_id = s.sex_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id
            LEFT JOIN visits v ON p.patient_id = v.patient_id AND v.visit_id = %s
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE p.patient_id = %s
            LIMIT 1
        """
        
        patient_result = Database.execute_query(
            fetch_query, 
            (visit_id, patient_id), 
            fetch_one=True
        )
        
        # Format patient
        visit_data = {
            'visit_datetime': patient_result['visit_datetime'],
            'check_in_datetime': patient_result['check_in_datetime'],
            'status_name': patient_result['status_name'],
            'notes': patient_result['notes'],
            'followup_date': patient_result['followup_date']
        }
        
        doctor_data = None
        if patient_result.get('doctor_first_name'):
            doctor_data = {
                'first_name': patient_result['doctor_first_name'],
                'last_name': patient_result['doctor_last_name']
            }
        
        patient = format_patient_response(patient_result, visit_data, doctor_data)
        
        # Step 7: Format invoice
        from utils.formatters import format_invoice_id
        
        invoice = {
            'id': format_invoice_id(bill_id),
            'patientId': patient_id,
            'patientName': f"{data['firstName']} {data['lastName']}",
            'phone': data.get('phone', ''),
            'email': data.get('email', ''),
            'assignedDoctor': data.get('assignedDoctor', ''),
            'date': visit_datetime.isoformat(),
            'items': [
                {
                    'description': 'Consultation Fee',
                    'quantity': 1,
                    'unitPrice': consultation_price
                }
            ],
            'subtotal': subtotal,
            'tax': tax,
            'total': total,
            'status': 'pending',
            'paymentMethod': None,
            'paidDate': None
        }
        
        # Return both patient and invoice
        return jsonify({
            'patient': patient,
            'invoice': invoice
        }), 201
        
    except Exception as e:
        print(f"Error creating patient: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to register patient'}), 500
    

@patients_bp.route('/api/patients/<patient_id>', methods=['GET'])
@token_required
def get_patient(current_user, patient_id):
    """
    Get single patient by ID
    
    Response:
        Patient object with latest visit information
    """
    try:
        query = """
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.date_of_birth,
                p.phone,
                p.email,
                p.address,
                p.emergency_contact_name,
                p.emergency_contact_relationship,
                p.emergency_contact_phone,
                s.name as sex_name,
                gi.name as gender_identity_name,
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes,
                v.followup_date,
                vs.name as status_name,
                d.first_name as doctor_first_name,
                d.last_name as doctor_last_name
            FROM patients p
            LEFT JOIN sex s ON p.sex_id = s.sex_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id
            LEFT JOIN (
                SELECT v1.*
                FROM visits v1
                INNER JOIN (
                    SELECT patient_id, MAX(visit_datetime) as max_date
                    FROM visits
                    WHERE patient_id = %s
                    GROUP BY patient_id
                ) v2 ON v1.patient_id = v2.patient_id 
                    AND v1.visit_datetime = v2.max_date
            ) v ON p.patient_id = v.patient_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE p.patient_id = %s
            LIMIT 1
        """
        
        result = Database.execute_query(query, (patient_id, patient_id), fetch_one=True)
        
        if not result:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Prepare visit data
        visit_data = None
        if result.get('visit_id'):
            visit_data = {
                'visit_datetime': result['visit_datetime'],
                'check_in_datetime': result['check_in_datetime'],
                'status_name': result['status_name'],
                'notes': result['notes'],
                'followup_date': result['followup_date']
            }
        
        # Prepare doctor data
        doctor_data = None
        if result.get('doctor_first_name'):
            doctor_data = {
                'first_name': result['doctor_first_name'],
                'last_name': result['doctor_last_name']
            }
        
        # Format patient
        patient = format_patient_response(result, visit_data, doctor_data)
        
        return jsonify(patient), 200
        
    except Exception as e:
        print(f"Error getting patient: {e}")
        return jsonify({'error': 'Failed to retrieve patient'}), 500
    

@patients_bp.route('/api/patients/<patient_id>/status', methods=['PATCH'])
@token_required
def update_patient_status(current_user, patient_id):
    """
    Update patient's visit status (for check-in)
    
    Request Body:
        {
            "status": "waiting" | "checked-in" | "completed"
        }
    
    Response:
        Updated patient object
    """
    try:
        data = request.get_json()
        
        if not data or 'status' not in data:
            return jsonify({'error': 'Status is required'}), 400
        
        new_status = data['status']
        
        valid_statuses = ['waiting', 'checked-in', 'completed']
        if new_status not in valid_statuses:
            return jsonify({'error': 'Invalid status'}), 400
        
        # getting status_id from visit_status table
        status_query = "SELECT status_id FROM visit_status WHERE name = %s"
        status_result = Database.execute_query(status_query, (new_status,), fetch_one=True)
        
        if not status_result:
            return jsonify({'error': 'Invalid status'}), 400
        
        status_id = status_result['status_id']
        
        # getting the most recent visit_id for this patient
        get_visit_query = """
            SELECT visit_id
            FROM visits
            WHERE patient_id = %s
            ORDER BY visit_datetime DESC
            LIMIT 1
        """
        
        visit_result = Database.execute_query(get_visit_query, (patient_id,), fetch_one=True)
        
        if not visit_result:
            return jsonify({'error': 'No visit found for this patient'}), 404
        
        visit_id = visit_result['visit_id']
        
        # updating specific visit
        update_query = """
            UPDATE visits
            SET status_id = %s,
                check_in_datetime = CASE 
                    WHEN %s = 2 AND check_in_datetime IS NULL 
                    THEN NOW() 
                    ELSE check_in_datetime 
                END
            WHERE visit_id = %s
        """
        
        Database.execute_query(update_query, (status_id, status_id, visit_id), commit=True)
        
        # Fetch and return updated patient
        query = """
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.date_of_birth,
                p.phone,
                p.email,
                p.address,
                p.emergency_contact_name,
                p.emergency_contact_relationship,
                p.emergency_contact_phone,
                s.name as sex_name,
                gi.name as gender_identity_name,
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes,
                v.followup_date,
                vs.name as status_name,
                d.first_name as doctor_first_name,
                d.last_name as doctor_last_name
            FROM patients p
            LEFT JOIN sex s ON p.sex_id = s.sex_id
            LEFT JOIN visits v ON p.patient_id = v.patient_id AND v.visit_id = %s
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE p.patient_id = %s
            LIMIT 1
        """
        
        result = Database.execute_query(query, (visit_id, patient_id), fetch_one=True)
        
        if not result:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Format response
        visit_data = {
            'visit_datetime': result['visit_datetime'],
            'check_in_datetime': result['check_in_datetime'],
            'status_name': result['status_name'],
            'notes': result['notes'],
            'followup_date': result['followup_date']
        }
        
        doctor_data = None
        if result.get('doctor_first_name'):
            doctor_data = {
                'first_name': result['doctor_first_name'],
                'last_name': result['doctor_last_name']
            }
        
        patient = format_patient_response(result, visit_data, doctor_data)
        
        return jsonify(patient), 200
        
    except Exception as e:
        print(f"Error updating patient status: {e}")
        return jsonify({'error': 'Failed to update patient status'}), 500


@patients_bp.route('/api/patients/queue', methods=['GET'])
@token_required
def get_queue_patients(current_user):
    """
    Get patients in queue (waiting or checked-in status)
    
    Response:
        Array of patient objects with status "waiting" or "checked-in"
    """
    try:
        query = """
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.date_of_birth,
                p.phone,
                p.email,
                p.address,
                p.emergency_contact_name,
                p.emergency_contact_relationship,
                p.emergency_contact_phone,
                s.name as sex_name,
                gi.name as gender_identity_name,
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes,
                vs.name as status_name,
                d.first_name as doctor_first_name,
                d.last_name as doctor_last_name
            FROM patients p
            LEFT JOIN sex s ON p.sex_id = s.sex_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id
            LEFT JOIN (
                SELECT v1.*
                FROM visits v1
                INNER JOIN (
                    SELECT patient_id, MAX(visit_datetime) as max_date
                    FROM visits
                    GROUP BY patient_id
                ) v2 ON v1.patient_id = v2.patient_id 
                    AND v1.visit_datetime = v2.max_date
            ) v ON p.patient_id = v.patient_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE vs.name IN ('waiting', 'checked-in')
            ORDER BY v.visit_datetime ASC
        """
        
        results = Database.execute_query(query)
        
        patients = []
        for row in results:
            visit_data = {
                'visit_datetime': row['visit_datetime'],
                'check_in_datetime': row['check_in_datetime'],
                'status_name': row['status_name'],
                'notes': row['notes']
            }
            
            doctor_data = None
            if row.get('doctor_first_name'):
                doctor_data = {
                    'first_name': row['doctor_first_name'],
                    'last_name': row['doctor_last_name']
                }
            
            patient = format_patient_response(row, visit_data, doctor_data)
            patients.append(patient)
        
        return jsonify(patients), 200
        
    except Exception as e:
        print(f"Error getting queue patients: {e}")
        return jsonify({'error': 'Failed to retrieve queue'}), 500


@patients_bp.route('/api/dashboard/stats', methods=['GET'])
@token_required
def get_dashboard_stats(current_user):
    """
    Get dashboard statistics
    
    Response:
        {
            "total": 100,
            "checkedIn": 12,
            "waiting": 8,
            "completed": 25,
            "newToday": 5
        }
    """
    try:
        query = """
            SELECT 
                COUNT(DISTINCT p.patient_id) as total,
                SUM(CASE WHEN vs.name = 'checked-in' THEN 1 ELSE 0 END) as checked_in,
                SUM(CASE WHEN vs.name = 'waiting' THEN 1 ELSE 0 END) as waiting,
                SUM(CASE WHEN vs.name = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN DATE(v.visit_datetime) = CURDATE() THEN 1 ELSE 0 END) as new_today
            FROM patients p
            LEFT JOIN (
                SELECT v1.*
                FROM visits v1
                INNER JOIN (
                    SELECT patient_id, MAX(visit_datetime) as max_date
                    FROM visits
                    GROUP BY patient_id
                ) v2 ON v1.patient_id = v2.patient_id 
                    AND v1.visit_datetime = v2.max_date
            ) v ON p.patient_id = v.patient_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
        """
        
        result = Database.execute_query(query, fetch_one=True)
        
        from utils.formatters import format_dashboard_stats
        
        stats = format_dashboard_stats({
            'total': result['total'] or 0,
            'checked_in': result['checked_in'] or 0,
            'waiting': result['waiting'] or 0,
            'completed': result['completed'] or 0,
            'new_today': result['new_today'] or 0
        })
        
        return jsonify(stats), 200
        
    except Exception as e:
        print(f"Error getting dashboard stats: {e}")
        return jsonify({'error': 'Failed to retrieve statistics'}), 500


@patients_bp.route('/api/patients/<patient_id>', methods=['PATCH'])
@token_required
def update_patient(current_user, patient_id):
    """
    Update patient information
    
    Request Body:
        {
            "name": "John Doe Updated",
            "phone": "+63-917-999-9999",
            "age": 36,
            "gender": "Male",
            "assignedDoctor": "Dr. Policarpio",
            "hasFollowUp": true,
            "followUpDate": "2026-02-15",
            "status": "checked-in",
            "medicalNotes": "Updated notes"
        }
    
    Response:
        Updated patient object
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        patient_updates = []
        patient_params = []
        
        # name update (splitting into first and last)
        if data.get('name'):
            name_parts = data['name'].split(' ', 1)
            if len(name_parts) >= 1:
                patient_updates.append("first_name = %s")
                patient_params.append(name_parts[0])
            if len(name_parts) >= 2:
                patient_updates.append("last_name = %s")
                patient_params.append(name_parts[1])
        
        if data.get('phone'):
            patient_updates.append("phone = %s")
            patient_params.append(data['phone'])
        
        if data.get('email'):
            patient_updates.append("email = %s")
            patient_params.append(data['email'])
        
        if data.get('address'):
            patient_updates.append("address = %s")
            patient_params.append(data['address'])
        
        if data.get('emergencyContact'):
            patient_updates.append("emergency_contact_name = %s")
            patient_params.append(data['emergencyContact'])
        
        if data.get('emergencyContactRelationship'):
            patient_updates.append("emergency_contact_relationship = %s")
            patient_params.append(data['emergencyContactRelationship'])
        
        if data.get('emergencyPhone'):
            patient_updates.append("emergency_contact_phone = %s")
            patient_params.append(data['emergencyPhone'])
        
        # Handle biological sex update
        if data.get('sex'):
            sex = data['sex'].lower()
            sex_map = {'male': 1, 'female': 2}
            if sex in sex_map:
                patient_updates.append("sex_id = %s")
                patient_params.append(sex_map[sex])
        
        # Handle gender identity update
        if data.get('gender'):
            gender = data['gender'].lower()
            gender_map = {
                'male': 1,
                'female': 2,
                'non-binary': 3,
                'prefer not to say': 4,
                'other': 5
            }
            if gender in gender_map:
                patient_updates.append("gender_identity_id = %s")
                patient_params.append(gender_map[gender])
        
        if patient_updates:
            patient_query = f"""
                UPDATE patients
                SET {', '.join(patient_updates)}
                WHERE patient_id = %s
            """
            patient_params.append(patient_id)
            Database.execute_query(patient_query, tuple(patient_params), commit=True)
        
        # getting the most recent visit for the patient
        visit_query = """
            SELECT visit_id
            FROM visits
            WHERE patient_id = %s
            ORDER BY visit_datetime DESC
            LIMIT 1
        """
        visit_result = Database.execute_query(visit_query, (patient_id,), fetch_one=True)
        
        if visit_result:
            visit_id = visit_result['visit_id']
            
            visit_updates = []
            visit_params = []
            
            # updating doctor
            if data.get('assignedDoctor'):
                doctor_name_parts = data['assignedDoctor'].split(' ', 1)
                if len(doctor_name_parts) == 2:
                    doctor_query = """
                        SELECT doctor_id 
                        FROM doctors 
                        WHERE first_name = %s AND last_name = %s
                        LIMIT 1
                    """
                    doctor_result = Database.execute_query(
                        doctor_query, 
                        (doctor_name_parts[0], doctor_name_parts[1]), 
                        fetch_one=True
                    )
                    if doctor_result:
                        visit_updates.append("doctor_id = %s")
                        visit_params.append(doctor_result['doctor_id'])
            
            # updating status
            if data.get('status'):
                status_query = "SELECT status_id FROM visit_status WHERE name = %s LIMIT 1"
                status_result = Database.execute_query(status_query, (data['status'],), fetch_one=True)
                if status_result:
                    visit_updates.append("status_id = %s")
                    visit_params.append(status_result['status_id'])
            
            # updating follow-up
            if 'hasFollowUp' in data:
                if data['hasFollowUp'] and data.get('followUpDate'):
                    visit_updates.append("followup_date = %s")
                    visit_params.append(data['followUpDate'])
                elif not data['hasFollowUp']:
                    visit_updates.append("followup_date = NULL")
            
            # updating medical notes
            if 'medicalNotes' in data:
                visit_updates.append("notes = %s")
                visit_params.append(data['medicalNotes'])
            
            # updating visits table if there are changes
            if visit_updates:
                visit_update_query = f"""
                    UPDATE visits
                    SET {', '.join(visit_updates)}
                    WHERE visit_id = %s
                """
                visit_params.append(visit_id)
                Database.execute_query(visit_update_query, tuple(visit_params), commit=True)
        
        fetch_query = """
            SELECT 
                p.patient_id,
                p.first_name,
                p.last_name,
                p.date_of_birth,
                p.phone,
                p.email,
                p.address,
                p.emergency_contact_name,
                p.emergency_contact_relationship,
                p.emergency_contact_phone,
                s.name as sex_name,
                gi.name as gender_identity_name,
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes,
                v.followup_date,
                vs.name as status_name,
                d.first_name as doctor_first_name,
                d.last_name as doctor_last_name
            FROM patients p
            LEFT JOIN sex s ON p.sex_id = s.sex_id
            LEFT JOIN gender_identities gi ON p.gender_identity_id = gi.gender_identity_id
            LEFT JOIN (
                SELECT v1.*
                FROM visits v1
                INNER JOIN (
                    SELECT patient_id, MAX(visit_datetime) as max_date
                    FROM visits
                    WHERE patient_id = %s
                    GROUP BY patient_id
                ) v2 ON v1.patient_id = v2.patient_id 
                    AND v1.visit_datetime = v2.max_date
            ) v ON p.patient_id = v.patient_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE p.patient_id = %s
            LIMIT 1
        """
        
        result = Database.execute_query(fetch_query, (patient_id, patient_id), fetch_one=True)
        
        if not result:
            return jsonify({'error': 'Patient not found'}), 404
        
        # formatting patient
        visit_data = None
        if result.get('visit_id'):
            visit_data = {
                'visit_datetime': result['visit_datetime'],
                'check_in_datetime': result['check_in_datetime'],
                'status_name': result['status_name'],
                'notes': result['notes'],
                'followup_date': result['followup_date']
            }
        
        doctor_data = None
        if result.get('doctor_first_name'):
            doctor_data = {
                'first_name': result['doctor_first_name'],
                'last_name': result['doctor_last_name']
            }
        
        patient = format_patient_response(result, visit_data, doctor_data)
        
        return jsonify(patient), 200
        
    except Exception as e:
        print(f"Error updating patient: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update patient'}), 500


@patients_bp.route('/api/patients/<patient_id>', methods=['DELETE'])
@token_required
def delete_patient(current_user, patient_id):
    """
    Delete a patient and all related records
    
    Response:
        {
            "success": true,
            "message": "Patient deleted successfully"
        }
    """
    try:
        # checking if patient exists
        check_query = "SELECT patient_id FROM patients WHERE patient_id = %s LIMIT 1"
        patient = Database.execute_query(check_query, (patient_id,), fetch_one=True)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        # Delete in correct order due to foreign key constraints
        # 1. Delete bill_services first
        Database.execute_query(
            "DELETE FROM bill_services WHERE bill_id IN (SELECT bill_id FROM bills WHERE patient_id = %s)",
            (patient_id,),
            commit=True
        )
        
        # 2. Delete bills
        Database.execute_query(
            "DELETE FROM bills WHERE patient_id = %s",
            (patient_id,),
            commit=True
        )
        
        # 3. Delete diagnoses
        Database.execute_query(
            "DELETE FROM diagnoses WHERE visit_id IN (SELECT visit_id FROM visits WHERE patient_id = %s)",
            (patient_id,),
            commit=True
        )
        
        # 4. Delete prescriptions
        Database.execute_query(
            "DELETE FROM prescriptions WHERE visit_id IN (SELECT visit_id FROM visits WHERE patient_id = %s)",
            (patient_id,),
            commit=True
        )
        
        # 5. Delete visits
        Database.execute_query(
            "DELETE FROM visits WHERE patient_id = %s",
            (patient_id,),
            commit=True
        )
        
        # 6. Finally delete patient
        Database.execute_query(
            "DELETE FROM patients WHERE patient_id = %s",
            (patient_id,),
            commit=True
        )
        
        return jsonify({
            'success': True,
            'message': 'Patient deleted successfully'
        }), 200
        
    except Exception as e:
        print(f"Error deleting patient: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to delete patient'}), 500