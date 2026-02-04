from flask import Blueprint, request, jsonify
from config import Database
from utils.auth import token_required
from utils.formatters import format_invoice_response, format_invoice_id
from datetime import datetime
import uuid

billing_bp = Blueprint('billing', __name__)


@billing_bp.route('/api/invoices', methods=['GET'])
@token_required
def get_invoices(current_user):
    """
    Get all invoices/bills with filtering
    
    Query Parameters:
        status: Filter by payment status (paid, pending, overdue)
        search: Search by invoice ID or patient name
    
    Response:
        Array of invoice objects
    """
    try:
        # getting query parameters
        status_filter = request.args.get('status')
        search_query = request.args.get('search')
        
        query = """
            SELECT 
                b.bill_id,
                b.patient_id,
                b.visit_id,
                b.subtotal,
                b.tax,
                b.amount_total,
                b.status,
                b.payment_method_id,
                b.payment_date,
                b.billing_date,
                p.first_name,
                p.last_name,
                p.phone,
                p.email,
                pm.name as payment_method_name,
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                vs.name as visit_status_name        -- ← ADD THIS LINE
            FROM bills b
            LEFT JOIN patients p ON b.patient_id = p.patient_id
            LEFT JOIN payment_methods pm ON b.payment_method_id = pm.method_id
            LEFT JOIN visits v ON b.visit_id = v.visit_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            WHERE p.is_active = TRUE
        """
        
        params = []
        
        # status filter
        if status_filter:
            query += " AND LOWER(b.status) = LOWER(%s)"
            params.append(status_filter)
        
        # search filter
        if search_query:
            query += """ AND (
                b.bill_id LIKE %s
                OR CONCAT(p.first_name, ' ', p.last_name) LIKE %s
            )"""
            search_pattern = f"%{search_query}%"
            params.append(search_pattern)
            params.append(search_pattern)
        
        # order by most recent first
        query += " ORDER BY b.billing_date DESC"
        
        results = Database.execute_query(query, tuple(params) if params else None)
        
        # getting bill services for each invoice
        invoices = []
        for bill in results:
            services_query = """
                SELECT service_name, amount, quantity
                FROM bill_services
                WHERE bill_id = %s
            """
            services = Database.execute_query(services_query, (bill['bill_id'],))
            
            # format patient data
            patient_data = {
                'first_name': bill['first_name'],
                'last_name': bill['last_name'],
                'phone': bill['phone'],
                'email': bill['email']
            }
            
            # format invoice
            invoice = format_invoice_response(bill, services, patient_data)
            invoices.append(invoice)
        
        return jsonify(invoices), 200
        
    except Exception as e:
        print(f"Error getting invoices: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to retrieve invoices'}), 500


@billing_bp.route('/api/invoices/<invoice_id>', methods=['GET'])
@token_required
def get_invoice(current_user, invoice_id):
    """
    Get single invoice by ID
    
    Response:
        Invoice object with line items
    """
    try:
        bill_id = invoice_id.replace('INV-', 'BILL-')
        
        # getting bill
        query = """
            SELECT 
                b.bill_id,
                b.patient_id,
                b.visit_id,
                b.subtotal,
                b.tax,
                b.amount_total,
                b.status,
                b.payment_method_id,
                b.payment_date,
                b.billing_date,
                p.first_name,
                p.last_name,
                p.phone,
                p.email,
                pm.name as payment_method_name,
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                vs.name as visit_status_name        -- ← ADD THIS LINE
            FROM bills b
            LEFT JOIN patients p ON b.patient_id = p.patient_id
            LEFT JOIN payment_methods pm ON b.payment_method_id = pm.method_id
            LEFT JOIN visits v ON b.visit_id = v.visit_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id  -- ← ADD THIS LINE
            WHERE b.bill_id = %s
            LIMIT 1
        """
        
        bill = Database.execute_query(query, (bill_id,), fetch_one=True)
        
        if not bill:
            return jsonify({'error': 'Invoice not found'}), 404
        
        # getting services
        services_query = """
            SELECT service_name, amount, quantity
            FROM bill_services
            WHERE bill_id = %s
        """
        services = Database.execute_query(services_query, (bill_id,))
        
        # format patient data
        patient_data = {
            'first_name': bill['first_name'],
            'last_name': bill['last_name'],
            'phone': bill['phone'],
            'email': bill['email']
        }
        
        # format invoice
        invoice = format_invoice_response(bill, services, patient_data)
        
        return jsonify(invoice), 200
        
    except Exception as e:
        print(f"Error getting invoice: {e}")
        return jsonify({'error': 'Failed to retrieve invoice'}), 500



@billing_bp.route('/api/patients/<patient_id>/visits', methods=['GET'])
@token_required
def get_patient_visits(current_user, patient_id):
    """
    Get all visits for a specific patient
    """
    try:
        query = """
            SELECT 
                v.visit_id,
                v.visit_datetime,
                v.check_in_datetime,
                v.notes as chief_complaint,
                v.followup_date,
                vs.name as status_name,
                vs.status_id,
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                dep.name as department_name,
                b.bill_id,
                b.amount_total,
                b.status as bill_status,
                (SELECT COUNT(*) FROM bill_services bs 
                 WHERE bs.bill_id = b.bill_id 
                 AND bs.service_name = 'Follow-up Visit') as is_followup
            FROM visits v
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            LEFT JOIN departments dep ON d.department_id = dep.department_id
            LEFT JOIN bills b ON v.visit_id = b.visit_id
            WHERE v.patient_id = %s
            ORDER BY v.visit_datetime DESC
        """
        
        visits = Database.execute_query(query, (patient_id,))
        
        # Format visits for frontend
        formatted_visits = []
        for visit in visits:
            if visit['is_followup'] and visit['is_followup'] > 0:
                reason = 'Follow-Up Visit'
            elif visit['chief_complaint']:
                reason = visit['chief_complaint']
            else:
                reason = 'Not specified'
            
            formatted_visit = {
                'visitId': visit['visit_id'],
                'visitDate': visit['visit_datetime'].strftime('%b %d, %Y %I:%M %p') if visit['visit_datetime'] else 'N/A',
                'checkInDate': visit['check_in_datetime'].strftime('%b %d, %Y %I:%M %p') if visit['check_in_datetime'] else None,
                'chiefComplaint': reason,
                'followupDate': visit['followup_date'].strftime('%b %d, %Y') if visit['followup_date'] else None,
                'statusName': visit['status_name'],
                'statusId': visit['status_id'],
                'doctorName': visit['doctor_name'] or 'Not assigned',
                'departmentName': visit['department_name'] or 'Not specified',
                'billId': visit['bill_id'],
                'billTotal': float(visit['amount_total']) if visit['amount_total'] else 0,
                'billStatus': visit['bill_status']
            }
            formatted_visits.append(formatted_visit)
        
        return jsonify(formatted_visits), 200
        
    except Exception as e:
        print(f"Error getting patient visits: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to retrieve patient visits'}), 500


@billing_bp.route('/api/invoices/<invoice_id>', methods=['PATCH'])
@token_required
def update_invoice(current_user, invoice_id):
    """
    Update invoice (mark as paid)
    
    Request Body:
        {
            "status": "paid",
            "paymentMethod": "Cash",
            "paidDate": "2026-01-26T15:00:00"
        }
    
    Response:
        Updated invoice object
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        bill_id = invoice_id.replace('INV-', 'BILL-')
        
        # getting payment method ID if provided
        payment_method_id = None
        if data.get('paymentMethod'):
            pm_query = "SELECT method_id FROM payment_methods WHERE name = %s LIMIT 1"
            pm_result = Database.execute_query(pm_query, (data['paymentMethod'],), fetch_one=True)
            if pm_result:
                payment_method_id = pm_result['method_id']
        
        # building update query
        update_fields = []
        params = []
        
        if data.get('status'):
            update_fields.append("status = %s")
            params.append(data['status'])
        
        if payment_method_id:
            update_fields.append("payment_method_id = %s")
            params.append(payment_method_id)
        
        if data.get('paidDate'):
            update_fields.append("payment_date = %s")
            params.append(data['paidDate'])
        elif data.get('status') == 'paid' or data.get('status') == 'Paid':
            update_fields.append("payment_date = NOW()")
        
        if not update_fields:
            return jsonify({'error': 'No fields to update'}), 400
        
        update_query = f"""
            UPDATE bills
            SET {', '.join(update_fields)}
            WHERE bill_id = %s
        """
        params.append(bill_id)
        
        Database.execute_query(update_query, tuple(params), commit=True)
        
        # fetching updated bill
        bill_id = invoice_id.replace('INV-', 'BILL-')
        
        query = """
            SELECT 
                b.bill_id,
                b.patient_id,
                b.visit_id,
                b.subtotal,
                b.tax,
                b.amount_total,
                b.status,
                b.payment_method_id,
                b.payment_date,
                b.billing_date,
                p.first_name,
                p.last_name,
                p.phone,
                p.email,
                pm.name as payment_method_name,
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                vs.name as visit_status_name        -- ← ADD THIS LINE
            FROM bills b
            LEFT JOIN patients p ON b.patient_id = p.patient_id
            LEFT JOIN payment_methods pm ON b.payment_method_id = pm.method_id
            LEFT JOIN visits v ON b.visit_id = v.visit_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            LEFT JOIN visit_status vs ON v.status_id = vs.status_id
            WHERE b.bill_id = %s
            LIMIT 1
        """
        
        bill = Database.execute_query(query, (bill_id,), fetch_one=True)
        
        # getting services
        services_query = """
            SELECT service_name, amount, quantity
            FROM bill_services
            WHERE bill_id = %s
        """
        services = Database.execute_query(services_query, (bill_id,))
        
        patient_data = {
            'first_name': bill['first_name'],
            'last_name': bill['last_name'],
            'phone': bill['phone'],
            'email': bill['email']
        }
        
        invoice = format_invoice_response(bill, services, patient_data)
        
        return jsonify(invoice), 200
        
    except Exception as e:
        print(f"Error updating invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to update invoice'}), 500


@billing_bp.route('/api/invoices', methods=['POST'])
@token_required
def create_invoice(current_user):
    """
    Add services to invoice (creates new if none exists)
    
    Request Body:
        {
            "patientId": "PAT-123456",
            "items": [
                {
                    "serviceId": "bloodtest",
                    "description": "Blood Test",
                    "quantity": 1,
                    "unitPrice": 75.00
                }
            ]
        }
    
    Response:
        Updated/created invoice object
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('patientId'):
            return jsonify({'error': 'Patient ID is required'}), 400
        
        if not data.get('items') or len(data['items']) == 0:
            return jsonify({'error': 'At least one service item is required'}), 400
        
        patient_id = data['patientId']
        
        # getting patient info
        patient_query = """
            SELECT first_name, last_name, phone, email
            FROM patients
            WHERE patient_id = %s
            LIMIT 1
        """
        patient = Database.execute_query(patient_query, (patient_id,), fetch_one=True)
        
        if not patient:
            return jsonify({'error': 'Patient not found'}), 404
        
        # ================================================================
        # CHECK IF PATIENT HAS EXISTING PENDING INVOICE FOR TODAY
        # ================================================================
        
        existing_invoice_query = """
            SELECT b.bill_id, b.visit_id, v.status_id
            FROM bills b
            INNER JOIN visits v ON b.visit_id = v.visit_id
            WHERE b.patient_id = %s 
            AND LOWER(b.status) = 'pending'
            AND DATE(b.billing_date) = CURDATE()
            ORDER BY b.billing_date DESC
            LIMIT 1
        """
        
        existing_invoice = Database.execute_query(
            existing_invoice_query, 
            (patient_id,), 
            fetch_one=True
        )
        
        # Check if we need to create a new visit
        # Create new visit ONLY if:
        # 1. No pending invoice exists for today
        # 
        # If there's a pending invoice (even if completed), add to it!
        should_create_new_visit = not existing_invoice
        
        if existing_invoice and not should_create_new_visit:
            # ============================================================
            # PATIENT HAS PENDING INVOICE WITH WAITING STATUS
            # ADD SERVICES TO EXISTING INVOICE AND VISIT
            # ============================================================
            
            bill_id = existing_invoice['bill_id']
            visit_id = existing_invoice['visit_id']
            
            print(f"Found existing WAITING invoice {bill_id} for patient {patient_id}")
            print(f"   Adding {len(data['items'])} service(s) to existing invoice...")
            
            # Add new services to existing invoice
            for item in data['items']:
                service_id = f"SVC-{uuid.uuid4().hex[:6].upper()}"
                
                # Check if service already exists on this invoice
                check_service_query = """
                    SELECT service_id, quantity, amount
                    FROM bill_services
                    WHERE bill_id = %s AND service_name = %s
                    LIMIT 1
                """
                
                existing_service = Database.execute_query(
                    check_service_query,
                    (bill_id, item['description']),
                    fetch_one=True
                )
                
                if existing_service:
                    # Service already exists - increase quantity
                    new_quantity = existing_service['quantity'] + item['quantity']
                    new_amount = item['unitPrice']
                    
                    update_service_query = """
                        UPDATE bill_services
                        SET quantity = %s,
                            amount = %s
                        WHERE service_id = %s
                    """
                    
                    Database.execute_query(
                        update_service_query,
                        (new_quantity, new_amount, existing_service['service_id']),
                        commit=True
                    )
                    
                    print(f"   ✓ Updated {item['description']} quantity to {new_quantity}")
                else:
                    # Add new service to invoice
                    service_query = """
                        INSERT INTO bill_services (
                            service_id, bill_id, service_name, amount, quantity
                        ) VALUES (%s, %s, %s, %s, %s)
                    """
                    
                    Database.execute_query(
                        service_query,
                        (service_id, bill_id, item['description'], item['unitPrice'], item['quantity']),
                        commit=True
                    )
                    
                    print(f"   ✓ Added {item['description']} to invoice")
            
            # Recalculate totals
            recalculate_query = """
                SELECT SUM(amount * quantity) as subtotal
                FROM bill_services
                WHERE bill_id = %s
            """
            
            total_result = Database.execute_query(recalculate_query, (bill_id,), fetch_one=True)
            subtotal = float(total_result['subtotal']) if total_result and total_result['subtotal'] else 0
            tax = subtotal * 0.1
            total = subtotal + tax
            
            # Update invoice totals
            update_totals_query = """
                UPDATE bills
                SET subtotal = %s,
                    tax = %s,
                    amount_total = %s
                WHERE bill_id = %s
            """
            
            Database.execute_query(
                update_totals_query,
                (subtotal, tax, total, bill_id),
                commit=True
            )
            
            print(f"   ✓ Updated totals: subtotal=₱{subtotal}, tax=₱{tax}, total=₱{total}")
            
        else:
            # ============================================================
            # CREATE NEW VISIT AND NEW INVOICE
            # (Either no pending invoice, or existing visit is completed)
            # ============================================================
            
            print(f"Creating NEW visit and invoice for patient {patient_id}")
            print(f"   Reason: {'No pending invoice' if not existing_invoice else 'Existing visit completed'}")
            
            # Get doctor_id from request, or copy from last visit
            doctor_id = data.get('doctorId')  # Get from frontend
            
            if not doctor_id:
                # No doctor specified - copy from most recent visit
                recent_visit_query = """
                    SELECT doctor_id
                    FROM visits
                    WHERE patient_id = %s
                    ORDER BY visit_datetime DESC
                    LIMIT 1
                """
                recent_visit = Database.execute_query(recent_visit_query, (patient_id,), fetch_one=True)
                doctor_id = recent_visit['doctor_id'] if recent_visit else 'DOC-000001'
            
            print(f"   ✓ Using doctor: {doctor_id}")
            
            # Get chief complaint from request
            chief_complaint = data.get('chiefComplaint', '')
            
            # Create NEW visit
            visit_id = f"VIS-{uuid.uuid4().hex[:6].upper()}"

            create_visit_query = """
                INSERT INTO visits (
                    visit_id, patient_id, doctor_id, visit_datetime, 
                    status_id, notes, created_at, created_by_user_id
                ) VALUES (%s, %s, %s, NOW(), 1, %s, NOW(), %s)
            """
            Database.execute_query(
                create_visit_query, 
                (visit_id, patient_id, doctor_id, chief_complaint, current_user['user_id']), 
                commit=True
            )
            
            print(f"   ✓ Chief complaint: {chief_complaint}")
            
            print(f"   ✓ Created new visit: {visit_id}")
            
            # Calculate totals
            subtotal = sum(item['quantity'] * item['unitPrice'] for item in data['items'])
            tax = subtotal * 0.1
            total = subtotal + tax
            
            # Create NEW bill
            bill_id = f"BILL-{uuid.uuid4().hex[:6].upper()}"
            
            bill_query = """
                INSERT INTO bills (
                    bill_id, visit_id, patient_id, subtotal, tax, amount_total,
                    status, billing_date, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, 'Pending', NOW(), NOW())
            """
            
            Database.execute_query(
                bill_query, 
                (bill_id, visit_id, patient_id, subtotal, tax, total), 
                commit=True
            )
            
            # Add line items
            for item in data['items']:
                service_id = f"SVC-{uuid.uuid4().hex[:6].upper()}"
                
                service_query = """
                    INSERT INTO bill_services (
                        service_id, bill_id, service_name, amount, quantity
                    ) VALUES (%s, %s, %s, %s, %s)
                """
                
                Database.execute_query(
                    service_query,
                    (service_id, bill_id, item['description'], item['unitPrice'], item['quantity']),
                    commit=True
                )
            
            print(f"   ✓ Created new invoice: {bill_id}")
        
        # ================================================================
        # FETCH AND RETURN THE INVOICE (existing or new)
        # ================================================================
        
        # Get all services for this invoice
        services_query = """
            SELECT service_name, amount, quantity
            FROM bill_services
            WHERE bill_id = %s
        """
        services = Database.execute_query(services_query, (bill_id,))
        
        # Get updated bill totals
        bill_query = """
            SELECT subtotal, tax, amount_total
            FROM bills
            WHERE bill_id = %s
            LIMIT 1
        """
        bill_totals = Database.execute_query(bill_query, (bill_id,), fetch_one=True)
        
        # Format and return invoice
        invoice_id = format_invoice_id(bill_id)
        
        invoice = {
            'id': invoice_id,
            'patientId': patient_id,
            'patientName': f"{patient['first_name']} {patient['last_name']}",
            'phone': patient['phone'],
            'email': patient['email'],
            'date': datetime.now().isoformat(),
            'items': [
                {
                    'description': service['service_name'],
                    'quantity': service['quantity'],
                    'unitPrice': float(service['amount'])
                }
                for service in services
            ],
            'subtotal': float(bill_totals['subtotal']),
            'tax': float(bill_totals['tax']),
            'total': float(bill_totals['amount_total']),
            'status': 'pending',
            'paymentMethod': None,
            'paidDate': None
        }
        
        return jsonify(invoice), 201
        
    except Exception as e:
        print(f"Error creating/updating invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to create invoice'}), 500
    

@billing_bp.route('/api/patients/<patient_id>/followup-check', methods=['GET'])
@token_required
def check_patient_followup(current_user, patient_id):
    """
    Check if patient has a follow-up appointment scheduled for today
    Checks ALL visits, not just the most recent one
    """
    try:
        # Check ALL visits for any follow-up scheduled for today
        query = """
            SELECT 
                v.visit_id,
                v.followup_date,
                v.doctor_id,
                v.notes as original_complaint,
                v.visit_datetime as original_visit_date,
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name,
                DATE(v.followup_date) = CURDATE() as is_today
            FROM visits v
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE v.patient_id = %s
            AND v.followup_date IS NOT NULL
            AND DATE(v.followup_date) = CURDATE()
            ORDER BY v.visit_datetime DESC
            LIMIT 1
        """
        
        result = Database.execute_query(query, (patient_id,), fetch_one=True)
        
        if result:
            return jsonify({
                'has_followup_today': True,
                'followup_date': result['followup_date'].strftime('%Y-%m-%d') if result['followup_date'] else None,
                'previous_visit_id': result['visit_id'],
                'previous_visit_date': result['original_visit_date'].strftime('%b %d, %Y') if result['original_visit_date'] else None,
                'original_complaint': result['original_complaint'],
                'previous_doctor_id': result['doctor_id'],
                'previous_doctor_name': result['doctor_name']
            }), 200
        else:
            return jsonify({
                'has_followup_today': False,
                'followup_date': None,
                'previous_visit_id': None,
                'previous_visit_date': None,
                'original_complaint': None,
                'previous_doctor_id': None,
                'previous_doctor_name': None
            }), 200
            
    except Exception as e:
        print(f"Error checking follow-up: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to check follow-up status'}), 500