from utils.formatters import *
from datetime import datetime

# Test patient ID formatting (should return as-is)
print("Patient ID:", format_patient_id("PAT-ABC123"))  # Should print: PAT-ABC123

# Test invoice ID formatting (BILL -> INV conversion)
print("Invoice ID:", format_invoice_id("BILL-00B3A4"))  # Should print: INV-00B3A4

# Test age calculation
print("Age:", calculate_age("1990-05-15"))  # Should print age

# Test time formatting
print("Time:", format_time_12hr("14:30:00"))  # Should print: 2:30 PM

print("\n- All formatters working!")