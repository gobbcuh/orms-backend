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
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name
            FROM bills b
            LEFT JOIN patients p ON b.patient_id = p.patient_id
            LEFT JOIN payment_methods pm ON b.payment_method_id = pm.method_id
            LEFT JOIN visits v ON b.visit_id = v.visit_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
            WHERE 1=1
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
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name
            FROM bills b
            LEFT JOIN patients p ON b.patient_id = p.patient_id
            LEFT JOIN payment_methods pm ON b.payment_method_id = pm.method_id
            LEFT JOIN visits v ON b.visit_id = v.visit_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
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
                CONCAT(d.first_name, ' ', d.last_name) as doctor_name
            FROM bills b
            LEFT JOIN patients p ON b.patient_id = p.patient_id
            LEFT JOIN payment_methods pm ON b.payment_method_id = pm.method_id
            LEFT JOIN visits v ON b.visit_id = v.visit_id
            LEFT JOIN doctors d ON v.doctor_id = d.doctor_id
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
    Create new invoice manually
    
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
        Created invoice object
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
        
        # getting or creating a visit for this patient
        visit_query = """
            SELECT visit_id, doctor_id
            FROM visits
            WHERE patient_id = %s
            ORDER BY visit_datetime DESC
            LIMIT 1
        """
        visit = Database.execute_query(visit_query, (patient_id,), fetch_one=True)
        
        visit_id = visit['visit_id'] if visit else None
        
        # if no visit exists, create one
        if not visit_id:
            visit_id = f"VIS-{uuid.uuid4().hex[:6].upper()}"
            create_visit_query = """
                INSERT INTO visits (
                    visit_id, patient_id, visit_datetime, status_id, 
                    created_at, created_by_user_id
                ) VALUES (%s, %s, NOW(), 1, NOW(), %s)
            """
            Database.execute_query(
                create_visit_query, 
                (visit_id, patient_id, current_user['user_id']), 
                commit=True
            )
        
        # calculating totals
        subtotal = sum(item['quantity'] * item['unitPrice'] for item in data['items'])
        tax = subtotal * 0.1
        total = subtotal + tax
        
        # creating bill
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
        
        # adding line items
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
        
        # formatting and returning invoice
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
                    'description': item['description'],
                    'quantity': item['quantity'],
                    'unitPrice': item['unitPrice']
                }
                for item in data['items']
            ],
            'subtotal': subtotal,
            'tax': tax,
            'total': total,
            'status': 'pending',
            'paymentMethod': None,
            'paidDate': None
        }
        
        return jsonify(invoice), 201
        
    except Exception as e:
        print(f"Error creating invoice: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to create invoice'}), 500