import mysql.connector
import csv
import os
from datetime import datetime

# DATABASE CONFIGURATION

DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'luckyroot@11',
    'database': 'orms_db',
    'charset': 'utf8mb4',
    'collation': 'utf8mb4_unicode_ci'
}

CSV_FOLDER = r'C:\Users\jajal\Desktop\Tech\OMS_dataset'

# ============================================================================

# HELPER FUNCTIONS

def connect_db():
    """Connect to MySQL database"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        print(" Connected to database successfully!")
        return conn
    except mysql.connector.Error as err:
        print(f" Error connecting to database: {err}")
        return None

def import_csv(cursor, table_name, csv_file, columns):
    """Import data from CSV file into specified table"""
    csv_path = os.path.join(CSV_FOLDER, csv_file)
    
    if not os.path.exists(csv_path):
        print(f" Warning: {csv_file} not found, skipping...")
        return 0
    
    print(f" Importing {csv_file} into {table_name}...")
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        csv_reader = csv.DictReader(f)
        rows_imported = 0
        
        for row in csv_reader:
            values = []
            for col in columns:
                value = row.get(col, None)
                if value == '':
                    value = None
                values.append(value)
            
            placeholders = ', '.join(['%s'] * len(columns))
            column_names = ', '.join(columns)
            
            sql = f"INSERT IGNORE INTO {table_name} ({column_names}) VALUES ({placeholders})"
            
            try:
                cursor.execute(sql, values)
                rows_imported += 1
            except mysql.connector.Error as err:
                print(f"   Error importing row: {err}")
                print(f"   Row data: {row}")
                continue
        
        print(f"   Imported {rows_imported} rows")
        return rows_imported

# ============================================================================

# MAIN IMPORT FUNCTION

def main():
    print("=" * 70)
    print(" ORMS Database CSV Import")
    print("=" * 70)
    print()
    
    conn = connect_db()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    try:
        # foreign key checks off temporarily
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        print(" Foreign key checks disabled")
        print()
        
        
        # ================================================================
        # IMPORTING DATA IN CORRECT ORDER (respects foreign key dependencies)
        
        total_rows = 0
        
        # I: lookup tables (no dependencies)
        
        print("I: Importing lookup tables...")
        print("-" * 70)
        
        # 1. sex
        total_rows += import_csv(cursor, 'sex', 'sex.csv', 
            ['sex_id', 'name'])

        # 2. visit_status
        total_rows += import_csv(cursor, 'visit_status', 'visit_status.csv', 
            ['status_id', 'name'])
        
        # 3. payment_methods
        total_rows += import_csv(cursor, 'payment_methods', 'payment_methods.csv', 
            ['method_id', 'name'])
        
        # 4. medications
        total_rows += import_csv(cursor, 'medications', 'medications.csv', 
            ['medication_id', 'name', 'generic_name', 'category', 'common_dose', 'common_frequency'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # II: departments (no dependencies)
        
        print("II: Importing departments...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'departments', 'departments.csv', 
            ['department_id', 'name', 'code', 'description', 'created_at'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # III: doctors (depends on: departments, sex)
        
        print("III: Importing doctors...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'doctors', 'doctors.csv', 
            ['doctor_id', 'first_name', 'last_name', 'license_number', 'sex_id', 
             'department_id', 'phone', 'email', 'hire_date', 'created_at'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # IV: patients (depends on: sex)
        
        print("IV: Importing patients...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'patients', 'patients.csv', 
            ['patient_id', 'first_name', 'last_name', 'date_of_birth', 'sex_id', 
             'phone', 'email', 'address', 'emergency_contact_name', 
             'emergency_contact_relationship', 'emergency_contact_phone', 'created_at'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # V: users (no dependencies)
        
        print("V: Importing users...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'users', 'users.csv', 
            ['user_id', 'username', 'password_hash', 'role', 'is_active', 
             'created_at', 'last_login'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # VI: visits (depends on: patients, doctors, visit_status, users)
        
        print("VI: Importing visits...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'visits', 'visits.csv', 
            ['visit_id', 'patient_id', 'doctor_id', 'visit_datetime', 
             'check_in_datetime', 'duration_minutes', 'chief_complaint', 
             'status_id', 'notes', 'created_at', 'created_by_user_id'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # VII: diagnoses (depends on: visits)
        
        print("VII: Importing diagnoses...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'diagnoses', 'diagnoses.csv', 
            ['diagnosis_id', 'visit_id', 'diagnosis_code', 'description', 'notes'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # VIII: prescriptions (depends on: visits, medications)
        
        print("VIII: Importing prescriptions...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'prescriptions', 'prescriptions.csv', 
            ['prescription_id', 'visit_id', 'medication_id', 'dosage', 'frequency', 
             'duration_days', 'instructions', 'prescribed_date', 'refills_allowed'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # IX: Bills (depends on: visits, patients)
        
        print("IX: Importing bills...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'bills', 'bills.csv', 
            ['bill_id', 'visit_id', 'patient_id', 'amount_total', 'status', 
             'billing_date', 'created_at'])
        
        print()
        
        # ────────────────────────────────────────────────────────────────
        # X: Bill Services (depends on: bills)
        
        print("X: Importing bill services...")
        print("-" * 70)
        
        total_rows += import_csv(cursor, 'bill_services', 'bill_services.csv', 
            ['service_id', 'bill_id', 'service_name', 'amount'])
        
        print()
        print("=" * 70)
        print(f" IMPORT COMPLETE. Total rows imported: {total_rows}")
        print("=" * 70)
        print()

        # ================================================================
        
        # foreign key checks on again when done
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        print(" Foreign key checks re-enabled")
        
        # committing all changes
        conn.commit()
        print("\n All changes committed successfully!")
        
    except mysql.connector.Error as err:
        print(f" Database error: {err}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()
        print("Database connection closed.")

if __name__ == "__main__":
    main()