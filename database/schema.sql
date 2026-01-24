-- ORMS Database Schema

-- drop database if exists (deletes everything)
DROP DATABASE IF EXISTS orms_db;

CREATE DATABASE orms_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE orms_db;
-- ============================================================================

-- LOOKUP TABLES (tables with no foreign keys)

-- 1. sex
CREATE TABLE sex (
    sex_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

-- 2. visit status
CREATE TABLE visit_status (
    status_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

-- 3. payment method
CREATE TABLE payment_methods (
    method_id INT PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

-- 4. medications
CREATE TABLE medications (
    medication_id INT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    generic_name VARCHAR(100) NOT NULL,
    category VARCHAR(50),
    common_dose VARCHAR(50),
    common_frequency VARCHAR(50)
);

-- ============================================================================

-- CORE ENTITY TABLES (Departments and Doctors)

-- 5. departments
CREATE TABLE departments (
    department_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    code VARCHAR(20) NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 6. doctors
CREATE TABLE doctors (
    doctor_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    license_number VARCHAR(50) NOT NULL UNIQUE,
    sex_id INT NOT NULL,
    department_id VARCHAR(20) NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    hire_date DATE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (sex_id) REFERENCES sex(sex_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
    
    -- indexes
    INDEX idx_doctor_department (department_id),
    INDEX idx_doctor_name (last_name, first_name)
);

-- ============================================================================

-- (Patients and Users)

-- 7. patients
CREATE TABLE patients (
    patient_id VARCHAR(20) PRIMARY KEY,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    date_of_birth DATE NOT NULL,
    sex_id INT NOT NULL,
    phone VARCHAR(20),
    email VARCHAR(100),
    address TEXT,
    emergency_contact_name VARCHAR(100),
    emergency_contact_relationship VARCHAR(50),
    emergency_contact_phone VARCHAR(20),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (sex_id) REFERENCES sex(sex_id),
    
    INDEX idx_patient_name (last_name, first_name),
    INDEX idx_patient_phone (phone),
    INDEX idx_patient_email (email)
);

-- 8. users (receptionists only)
CREATE TABLE users (
    user_id VARCHAR(20) PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'receptionist',
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_login DATETIME,
    
    INDEX idx_username (username)
);

-- ============================================================================

-- (Visits)

-- 9. visits
CREATE TABLE visits (
    visit_id VARCHAR(20) PRIMARY KEY,
    patient_id VARCHAR(20) NOT NULL,
    doctor_id VARCHAR(20) NOT NULL,
    visit_datetime DATETIME NOT NULL,
    check_in_datetime DATETIME,
    duration_minutes INT,
    chief_complaint TEXT,
    status_id INT NOT NULL DEFAULT 1,
    notes TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by_user_id VARCHAR(20) NOT NULL,
    
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE RESTRICT,
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id) ON DELETE RESTRICT,
    FOREIGN KEY (status_id) REFERENCES visit_status(status_id),
    FOREIGN KEY (created_by_user_id) REFERENCES users(user_id),
    
    INDEX idx_visit_patient (patient_id),
    INDEX idx_visit_doctor (doctor_id),
    INDEX idx_visit_datetime (visit_datetime),
    INDEX idx_visit_status (status_id),
    INDEX idx_visit_date (visit_datetime),
    
    -- constraints
    CHECK (duration_minutes > 0 OR duration_minutes IS NULL)
);

-- ============================================================================

-- (Clinical Data)

-- 10. diagnoses
CREATE TABLE diagnoses (
    diagnosis_id VARCHAR(20) PRIMARY KEY,
    visit_id VARCHAR(20) NOT NULL,
    diagnosis_code VARCHAR(20) NOT NULL,
    description TEXT NOT NULL,
    notes TEXT,
    
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE CASCADE,
    
    INDEX idx_diagnosis_visit (visit_id),
    INDEX idx_diagnosis_code (diagnosis_code)
);

-- 11. prescriptions
CREATE TABLE prescriptions (
    prescription_id VARCHAR(20) PRIMARY KEY,
    visit_id VARCHAR(20) NOT NULL,
    medication_id INT NOT NULL,
    dosage VARCHAR(50) NOT NULL,
    frequency VARCHAR(50) NOT NULL,
    duration_days INT NOT NULL,
    instructions TEXT,
    prescribed_date DATE NOT NULL,
    refills_allowed INT DEFAULT 0,
    
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE CASCADE,
    FOREIGN KEY (medication_id) REFERENCES medications(medication_id),
    
    INDEX idx_prescription_visit (visit_id),
    INDEX idx_prescription_medication (medication_id),
    
    CHECK (duration_days > 0),
    CHECK (refills_allowed >= 0)
);

-- ============================================================================

-- (BILLING TABLES)

-- 12. bills
CREATE TABLE bills (
    bill_id VARCHAR(20) PRIMARY KEY,
    visit_id VARCHAR(20) NOT NULL,
    patient_id VARCHAR(20) NOT NULL,
    amount_total DECIMAL(10, 2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'Pending',
    billing_date DATE NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (visit_id) REFERENCES visits(visit_id) ON DELETE RESTRICT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE RESTRICT,
    
    INDEX idx_bill_visit (visit_id),
    INDEX idx_bill_patient (patient_id),
    INDEX idx_bill_status (status),
    INDEX idx_bill_date (billing_date),
    
    CHECK (amount_total >= 0),
    CHECK (status IN ('Paid', 'Pending'))
);

-- 13. bill_services
CREATE TABLE bill_services (
    service_id VARCHAR(20) PRIMARY KEY,
    bill_id VARCHAR(20) NOT NULL,
    service_name VARCHAR(100) NOT NULL,
    amount DECIMAL(10, 2) NOT NULL,
    
    FOREIGN KEY (bill_id) REFERENCES bills(bill_id) ON DELETE CASCADE,
    
    INDEX idx_service_bill (bill_id),
    
    CHECK (amount >= 0)
);