from datetime import datetime, date

# ID FORMATTING

def format_patient_id(patient_id):
    """Format patient ID - returns as-is from database (PAT-XXX)"""
    return patient_id


def format_invoice_id(bill_id):
    """Format invoice ID: BILL-XXX -> INV-XXX"""
    if isinstance(bill_id, str):
        return bill_id.replace('BILL-', 'INV-')
    return f"INV-{str(bill_id).zfill(6)}"


# ============================================================================
# DATE/TIME FORMATTING

def calculate_age(birth_date):
    """Calculate age from birth date"""
    if not birth_date:
        return None
    
    if isinstance(birth_date, str):
        birth_date = datetime.strptime(birth_date, "%Y-%m-%d").date()
    
    today = date.today()
    age = today.year - birth_date.year
    
    # adjustment if birthday hasn't occurred yet within the year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    
    return age


def format_time_12hr(time_value):
    """Convert 24-hour time to 12-hour format: '14:30:00' -> '2:30 PM'"""
    if not time_value:
        return None
    
    if isinstance(time_value, str):
        time_value = datetime.strptime(time_value, "%H:%M:%S").time()
    
    # convert to datetime
    dt = datetime.combine(date.today(), time_value)
    return dt.strftime("%I:%M %p").lstrip('0')


def format_datetime_iso(dt_value):
    """Convert datetime to ISO 8601 format"""
    if not dt_value:
        return None
    
    if isinstance(dt_value, str):
        return dt_value
    
    return dt_value.isoformat()


def is_today(dt_value):
    """Check if a datetime is today"""
    if not dt_value:
        return False
    
    if isinstance(dt_value, str):
        dt_value = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
    
    return dt_value.date() == date.today()


def format_smart_datetime(dt_value):
    """
    Format datetime with smart display:
    - Today: "Today, 2:30 PM"
    - Yesterday: "Yesterday, 2:30 PM"
    - Older: "Jan 26, 2026 2:30 PM"
    """
    if not dt_value:
        return '-'
    
    if isinstance(dt_value, str):
        dt_value = datetime.fromisoformat(dt_value.replace('Z', '+00:00'))
    
    today = date.today()
    dt_date = dt_value.date()
    
    # Calculate days difference
    days_diff = (today - dt_date).days
    
    # Format time part (12-hour format)
    time_str = dt_value.strftime("%I:%M %p").lstrip('0')
    
    # Smart date formatting
    if days_diff == 0:
        return f"Today, {time_str}"
    elif days_diff == 1:
        return f"Yesterday, {time_str}"
    else:
        # Format as "Jan 26, 2026 2:30 PM"
        date_str = dt_value.strftime("%b %d, %Y")
        return f"{date_str} {time_str}"


# ============================================================================
# PATIENT FORMATTING

def format_patient_response(patient_data, visit_data=None, doctor_data=None):
    """
    Transform database patient record to frontend format
    
    Args:
        patient_data: Dictionary from patients table
        visit_data: Dictionary from visits table (optional)
        doctor_data: Dictionary from doctors table (optional)
    
    Returns:
        Dictionary matching frontend Patient interface
    """
    # extracting visit datetime
    visit_datetime = None
    if visit_data and visit_data.get('visit_datetime'):
        visit_datetime = visit_data['visit_datetime']
    
    # doctor name
    doctor_name = None
    if doctor_data:
        doctor_name = f"{doctor_data.get('first_name', '')} {doctor_data.get('last_name', '')}".strip()
    
    # follow-up date
    followup_date = None
    has_followup = False
    if visit_data and visit_data.get('followup_date'):
        followup_date = format_datetime_iso(visit_data['followup_date'])
        has_followup = True
    
    return {
        'id': patient_data.get('patient_id'),
        'name': f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip(),
        'age': calculate_age(patient_data.get('date_of_birth')),
        'gender': patient_data.get('sex_name', 'Unknown'),
        'phone': patient_data.get('phone', ''),
        'email': patient_data.get('email', ''),
        'address': patient_data.get('address', ''),
        'emergencyContact': patient_data.get('emergency_contact_name', ''),
        'emergencyContactRelationship': patient_data.get('emergency_contact_relationship', ''),
        'emergencyPhone': patient_data.get('emergency_contact_phone', ''),
        'registrationTime': format_smart_datetime(visit_datetime) if visit_datetime else '-',
        'registrationDate': format_datetime_iso(visit_datetime) if visit_datetime else None,
        'status': visit_data.get('status_name', 'waiting') if visit_data else 'waiting',
        'assignedDoctor': doctor_name,
        'hasFollowUp': has_followup,
        'followUpDate': followup_date,
        'medicalNotes': visit_data.get('notes', '') if visit_data else '',
        'isNew': is_today(visit_datetime) if visit_datetime else False,
    }


# ============================================================================
# INVOICE/BILLING FORMATTING

def format_invoice_response(bill_data, services_data=None, patient_data=None):
    """
    Transform database bill record to frontend invoice format
    
    Args:
        bill_data: Dictionary from bills table
        services_data: List of dictionaries from bill_services table
        patient_data: Dictionary from patients table
    
    Returns:
        Dictionary matching frontend Invoice interface
    """
    # patient name
    patient_name = "Unknown Patient"
    if patient_data:
        patient_name = f"{patient_data.get('first_name', '')} {patient_data.get('last_name', '')}".strip()
    
    # line items
    items = []
    if services_data:
        for service in services_data:
            items.append({
                'description': service.get('service_name', ''),
                'quantity': service.get('quantity', 1),
                'unitPrice': float(service.get('amount', 0)),
            })
    
    # payment method
    payment_method = None
    if bill_data.get('payment_method_name'):
        payment_method = bill_data['payment_method_name']
    
    # paid date
    paid_date = None
    if bill_data.get('payment_date'):
        paid_date = format_datetime_iso(bill_data['payment_date'])
    
    return {
        'id': bill_data.get('bill_id'),
        'patientId': bill_data.get('patient_id'),
        'patientName': patient_name,
        'phone': patient_data.get('phone', '') if patient_data else '',
        'email': patient_data.get('email', '') if patient_data else '',
        'assignedDoctor': bill_data.get('doctor_name', ''),
        'date': format_datetime_iso(bill_data.get('billing_date')),
        'items': items,
        'subtotal': float(bill_data.get('subtotal', 0)),
        'tax': float(bill_data.get('tax', 0)),
        'total': float(bill_data.get('amount_total', 0)),
        'status': bill_data.get('status', 'pending').lower(),
        'paymentMethod': payment_method,
        'paidDate': paid_date,
    }


# ============================================================================
# STATS FORMATTING

def format_dashboard_stats(stats_data):
    """Format dashboard statistics"""
    return {
        'total': stats_data.get('total', 0),
        'checkedIn': stats_data.get('checked_in', 0),
        'waiting': stats_data.get('waiting', 0),
        'completed': stats_data.get('completed', 0),
        'newToday': stats_data.get('new_today', 0),
    }


# ============================================================================
# REFERENCE DATA FORMATTING

def format_doctor_name(first_name, last_name):
    """Format doctor name"""
    return f"{first_name} {last_name}".strip()


def format_service_response(service_data):
    """Format service catalog item"""
    return {
        'id': service_data.get('service_id'),
        'name': service_data.get('name'),
        'price': float(service_data.get('price', 0)),
    }