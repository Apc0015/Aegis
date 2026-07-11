-- ============================================================================
-- MEDICAL COMPANY DATABASE SCHEMA
-- Organization: 500 Employees, 10 Departments
-- Compliance: HIPAA-ready with PII/PHI separation
-- Created: April 28, 2026
-- ============================================================================

-- ============================================================================
-- PART 1: ORGANIZATION STRUCTURE
-- ============================================================================

-- Locations (office/facility locations)
CREATE TABLE IF NOT EXISTS locations (
    location_id INTEGER PRIMARY KEY AUTOINCREMENT,
    location_name TEXT NOT NULL UNIQUE,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    zip_code TEXT NOT NULL,
    phone TEXT,
    manager_id INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Departments (10 departments)
CREATE TABLE IF NOT EXISTS departments (
    department_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_name TEXT NOT NULL UNIQUE,
    description TEXT,
    head_id INTEGER,
    location_id INTEGER,
    budget REAL,
    fiscal_year INTEGER DEFAULT 2026,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (head_id) REFERENCES employees(employee_id)
);

-- Teams (sub-teams within departments)
CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    team_lead_id INTEGER,
    location_id INTEGER,
    budget REAL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    FOREIGN KEY (team_lead_id) REFERENCES employees(employee_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- ============================================================================
-- PART 2: EMPLOYEES & STAFFING
-- ============================================================================

-- Employees (500 total - extends existing HR DB)
CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    department_id INTEGER NOT NULL,
    team_id INTEGER,
    job_title TEXT NOT NULL,
    employment_type TEXT NOT NULL CHECK (employment_type IN ('FT', 'PT', 'Contract', 'Temporary')),
    start_date DATE NOT NULL,
    end_date DATE,
    manager_id TEXT,
    salary REAL,
    salary_grade TEXT,
    location_id INTEGER,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'on_leave', 'terminated')),
    ssn_encrypted TEXT,  -- Encrypted SSN (not plain text)
    date_of_birth DATE,
    gender TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    FOREIGN KEY (team_id) REFERENCES teams(team_id),
    FOREIGN KEY (manager_id) REFERENCES employees(employee_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- Professional Certifications (medical licenses, degrees)
CREATE TABLE IF NOT EXISTS certifications (
    cert_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    certification_name TEXT NOT NULL,
    certification_number TEXT,
    issuing_authority TEXT,
    issue_date DATE NOT NULL,
    expiration_date DATE,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'pending', 'suspended')),
    is_medical_license BOOLEAN DEFAULT 0,  -- 1 for MD, RN, etc.
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
);

-- Employee Roles & Responsibilities
CREATE TABLE IF NOT EXISTS employee_roles (
    role_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    role_name TEXT NOT NULL,
    role_description TEXT,
    department_id INTEGER NOT NULL,
    is_primary BOOLEAN DEFAULT 0,
    start_date DATE NOT NULL,
    end_date DATE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- Reporting Hierarchy (org chart)
CREATE TABLE IF NOT EXISTS reporting_hierarchy (
    hierarchy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    manager_id TEXT NOT NULL,
    level_in_org INTEGER,
    effective_date DATE DEFAULT CURRENT_DATE,
    end_date DATE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (manager_id) REFERENCES employees(employee_id)
);

-- Medical Staff Specialties (for doctors, nurses, specialists)
CREATE TABLE IF NOT EXISTS medical_specialties (
    specialty_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    specialty_name TEXT NOT NULL,
    board_certified BOOLEAN DEFAULT 0,
    years_of_experience INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
);

-- ============================================================================
-- PART 3: PAYROLL & COMPENSATION
-- ============================================================================

-- Payroll Records
CREATE TABLE IF NOT EXISTS payroll (
    payroll_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    pay_period_start DATE NOT NULL,
    pay_period_end DATE NOT NULL,
    gross_salary REAL NOT NULL,
    federal_tax REAL,
    state_tax REAL,
    social_security REAL,
    medicare REAL,
    health_insurance_deduction REAL,
    other_deductions REAL,
    net_pay REAL NOT NULL,
    payment_date DATE,
    payment_method TEXT CHECK (payment_method IN ('Direct Deposit', 'Check')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'processed', 'cancelled')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
);

-- Employee Benefits Enrollment
CREATE TABLE IF NOT EXISTS employee_benefits (
    enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    benefit_name TEXT NOT NULL,
    benefit_type TEXT CHECK (benefit_type IN ('Health Insurance', '401k', 'FSA', 'HSA', 'Life Insurance', 'Disability', 'Other')),
    provider TEXT,
    enrollment_date DATE NOT NULL,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'pending', 'cancelled')),
    coverage_level TEXT,
    premium_amount REAL,
    employer_contribution REAL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
);

-- ============================================================================
-- PART 4: LEAVE & TIME OFF
-- ============================================================================

-- Leave Policies
CREATE TABLE IF NOT EXISTS leave_policies (
    policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
    policy_name TEXT NOT NULL,
    leave_type TEXT NOT NULL CHECK (leave_type IN ('Vacation', 'Sick', 'Medical', 'Maternity', 'Bereavement', 'Unpaid', 'Other')),
    days_per_year INTEGER,
    carry_over_max INTEGER,
    description TEXT,
    effective_date DATE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Leave Requests
CREATE TABLE IF NOT EXISTS leave_requests (
    request_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    leave_type TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    days_requested INTEGER NOT NULL,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled')),
    approved_by TEXT,
    submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    approved_at DATETIME,
    rejection_reason TEXT,
    notes TEXT,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (approved_by) REFERENCES employees(employee_id)
);

-- Employee Leave Balance
CREATE TABLE IF NOT EXISTS leave_balance (
    balance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    leave_type TEXT NOT NULL,
    total_accrued INTEGER,
    used_days INTEGER,
    remaining_days INTEGER,
    carry_over_days INTEGER,
    fiscal_year INTEGER DEFAULT 2026,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE,
    UNIQUE(employee_id, leave_type, fiscal_year)
);

-- ============================================================================
-- PART 5: PATIENT MANAGEMENT (Non-PII)
-- ============================================================================

-- Patients (de-identified for analytics)
CREATE TABLE IF NOT EXISTS patients (
    patient_id TEXT PRIMARY KEY,
    patient_age_group TEXT CHECK (patient_age_group IN ('0-18', '19-30', '31-50', '51-65', '65+')),
    gender TEXT CHECK (gender IN ('M', 'F', 'Other', 'Unknown')),
    blood_type TEXT,
    medical_conditions TEXT,  -- Comma-separated list
    medications_summary TEXT,
    patient_status TEXT DEFAULT 'active' CHECK (patient_status IN ('active', 'inactive', 'deceased', 'transferred')),
    primary_care_doctor_id TEXT,
    assigned_location_id INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_visit_date DATE,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (primary_care_doctor_id) REFERENCES employees(employee_id),
    FOREIGN KEY (assigned_location_id) REFERENCES locations(location_id)
);

-- Patient PII (ENCRYPTED - SEPARATE DATABASE)
CREATE TABLE IF NOT EXISTS patient_pii (
    pii_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL UNIQUE,
    first_name_encrypted TEXT NOT NULL,
    last_name_encrypted TEXT NOT NULL,
    ssn_encrypted TEXT UNIQUE,
    date_of_birth_encrypted DATE,
    phone_encrypted TEXT,
    email_encrypted TEXT,
    address_encrypted TEXT,
    city_encrypted TEXT,
    state_encrypted TEXT,
    zip_code_encrypted TEXT,
    emergency_contact_encrypted TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

-- Patient Contacts
CREATE TABLE IF NOT EXISTS patient_contacts (
    contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    contact_type TEXT CHECK (contact_type IN ('Emergency', 'Primary', 'Secondary')),
    contact_name TEXT,
    relationship TEXT,
    phone_encrypted TEXT,
    email_encrypted TEXT,
    address_encrypted TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

-- Insurance Information
CREATE TABLE IF NOT EXISTS insurance_info (
    insurance_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id TEXT NOT NULL,
    insurance_provider TEXT NOT NULL,
    policy_number_encrypted TEXT,
    group_number TEXT,
    member_id_encrypted TEXT,
    coverage_start_date DATE,
    coverage_end_date DATE,
    coverage_type TEXT CHECK (coverage_type IN ('Individual', 'Family', 'Group')),
    co_pay REAL,
    deductible REAL,
    max_out_of_pocket REAL,
    is_primary BOOLEAN DEFAULT 1,
    status TEXT DEFAULT 'active',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id) ON DELETE CASCADE
);

-- ============================================================================
-- PART 6: CLINICAL OPERATIONS
-- ============================================================================

-- Appointments
CREATE TABLE IF NOT EXISTS appointments (
    appointment_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    appointment_date DATE NOT NULL,
    appointment_time TIME NOT NULL,
    duration_minutes INTEGER DEFAULT 30,
    appointment_type TEXT CHECK (appointment_type IN ('Routine', 'Follow-up', 'Consultation', 'Procedure', 'Urgent')),
    status TEXT DEFAULT 'scheduled' CHECK (status IN ('scheduled', 'completed', 'cancelled', 'no-show', 'rescheduled')),
    location_id INTEGER,
    reason TEXT,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES employees(employee_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- Medical Records
CREATE TABLE IF NOT EXISTS medical_records (
    record_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    record_date DATE NOT NULL,
    doctor_id TEXT NOT NULL,
    appointment_id TEXT,
    diagnosis TEXT,
    icd_codes TEXT,  -- International Classification of Diseases codes
    treatment_plan TEXT,
    medications_prescribed TEXT,
    notes TEXT,
    is_confidential BOOLEAN DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES employees(employee_id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

-- Prescriptions
CREATE TABLE IF NOT EXISTS prescriptions (
    prescription_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    medication_name TEXT NOT NULL,
    ndc_code TEXT,  -- National Drug Code
    strength TEXT,
    dosage TEXT NOT NULL,
    frequency TEXT NOT NULL,
    route TEXT CHECK (route IN ('Oral', 'Injection', 'Inhalation', 'Topical', 'Other')),
    start_date DATE NOT NULL,
    end_date DATE,
    refills_allowed INTEGER DEFAULT 0,
    refills_remaining INTEGER,
    pharmacy_id INTEGER,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'completed', 'discontinued')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES employees(employee_id)
);

-- Lab Results
CREATE TABLE IF NOT EXISTS lab_results (
    result_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    test_date DATE NOT NULL,
    test_name TEXT NOT NULL,
    test_code TEXT,  -- LOINC code
    ordered_by_id TEXT NOT NULL,
    result_value TEXT,
    unit TEXT,
    reference_range TEXT,
    abnormal_flag TEXT CHECK (abnormal_flag IN ('Normal', 'Abnormal', 'Critical')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'received', 'reviewed', 'reported')),
    lab_id INTEGER,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (ordered_by_id) REFERENCES employees(employee_id)
);

-- Medical Facilities
CREATE TABLE IF NOT EXISTS medical_facilities (
    facility_id INTEGER PRIMARY KEY AUTOINCREMENT,
    facility_name TEXT NOT NULL,
    facility_type TEXT CHECK (facility_type IN ('Clinic', 'Hospital', 'Lab', 'Imaging Center', 'Pharmacy')),
    location_id INTEGER NOT NULL,
    capacity INTEGER,
    operating_hours TEXT,
    is_primary BOOLEAN DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- ============================================================================
-- PART 7: BILLING & REVENUE
-- ============================================================================

-- Billing Records
CREATE TABLE IF NOT EXISTS billing (
    billing_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    appointment_id TEXT,
    billing_date DATE NOT NULL,
    service_code TEXT,  -- CPT code
    service_description TEXT,
    quantity INTEGER DEFAULT 1,
    unit_price REAL NOT NULL,
    total_amount REAL NOT NULL,
    insurance_coverage REAL DEFAULT 0,
    patient_responsibility REAL,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'partial', 'paid', 'written_off', 'pending')),
    due_date DATE,
    paid_date DATE,
    payment_method TEXT,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id)
);

-- Insurance Claims Processing
CREATE TABLE IF NOT EXISTS claims_processing (
    claim_id TEXT PRIMARY KEY,
    billing_id TEXT NOT NULL,
    patient_id TEXT NOT NULL,
    insurance_id INTEGER NOT NULL,
    claim_date DATE NOT NULL,
    submitted_date DATE,
    claim_amount REAL NOT NULL,
    approved_amount REAL,
    denied_amount REAL,
    claim_status TEXT DEFAULT 'submitted' CHECK (claim_status IN ('submitted', 'acknowledged', 'processing', 'approved', 'partially_approved', 'denied', 'appealed')),
    denial_reason TEXT,
    appeal_count INTEGER DEFAULT 0,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (billing_id) REFERENCES billing(billing_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (insurance_id) REFERENCES insurance_info(insurance_id)
);

-- ============================================================================
-- PART 8: HR & TRAINING
-- ============================================================================

-- Training Records (mandatory compliance training)
CREATE TABLE IF NOT EXISTS training_records (
    training_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    training_name TEXT NOT NULL,
    training_type TEXT CHECK (training_type IN ('HIPAA', 'Safety', 'Compliance', 'Professional Dev', 'Mandatory', 'Other')),
    training_date DATE NOT NULL,
    completion_date DATE,
    certification_issued BOOLEAN DEFAULT 0,
    certification_expiry DATE,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'in_progress', 'completed', 'failed')),
    score INTEGER,
    provider TEXT,
    notes TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id) ON DELETE CASCADE
);

-- Performance Reviews
CREATE TABLE IF NOT EXISTS performance_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id TEXT NOT NULL,
    reviewer_id TEXT NOT NULL,
    review_date DATE NOT NULL,
    review_period_start DATE,
    review_period_end DATE,
    performance_rating TEXT CHECK (performance_rating IN ('Exceeds', 'Meets', 'Below', 'Needs Improvement')),
    overall_score INTEGER CHECK (overall_score >= 1 AND overall_score <= 5),
    strengths TEXT,
    areas_for_improvement TEXT,
    goals_for_next_period TEXT,
    comments TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (reviewer_id) REFERENCES employees(employee_id)
);

-- ============================================================================
-- PART 9: IT & OPERATIONS
-- ============================================================================

-- IT Assets
CREATE TABLE IF NOT EXISTS it_assets (
    asset_id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name TEXT NOT NULL,
    asset_type TEXT CHECK (asset_type IN ('Server', 'Workstation', 'Laptop', 'Mobile', 'Network', 'Software', 'License')),
    asset_tag TEXT UNIQUE,
    serial_number TEXT,
    assigned_to_id TEXT,
    location_id INTEGER,
    purchase_date DATE,
    warranty_expiry DATE,
    maintenance_contract BOOLEAN DEFAULT 0,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'retired', 'for_repair')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (assigned_to_id) REFERENCES employees(employee_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- IT Support Tickets
CREATE TABLE IF NOT EXISTS it_tickets (
    ticket_id TEXT PRIMARY KEY,
    submitted_by_id TEXT NOT NULL,
    assigned_to_id TEXT,
    ticket_title TEXT NOT NULL,
    ticket_description TEXT,
    ticket_type TEXT CHECK (ticket_type IN ('Bug', 'Support', 'Enhancement', 'Access Request')),
    priority TEXT DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'assigned', 'in_progress', 'resolved', 'closed')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_date DATETIME,
    resolution_notes TEXT,
    FOREIGN KEY (submitted_by_id) REFERENCES employees(employee_id),
    FOREIGN KEY (assigned_to_id) REFERENCES employees(employee_id)
);

-- System Uptime Monitoring
CREATE TABLE IF NOT EXISTS system_uptime (
    uptime_id INTEGER PRIMARY KEY AUTOINCREMENT,
    system_name TEXT NOT NULL,
    check_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT CHECK (status IN ('up', 'down', 'degraded')),
    response_time_ms INTEGER,
    error_message TEXT,
    recorded_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Inventory Management
CREATE TABLE IF NOT EXISTS inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    item_code TEXT UNIQUE,
    item_type TEXT CHECK (item_type IN ('Medical Supply', 'Equipment', 'Medication', 'Office Supply')),
    location_id INTEGER NOT NULL,
    quantity_on_hand INTEGER NOT NULL,
    minimum_quantity INTEGER,
    reorder_quantity INTEGER,
    unit_cost REAL,
    last_count_date DATE,
    status TEXT DEFAULT 'in_stock' CHECK (status IN ('in_stock', 'low_stock', 'out_of_stock', 'discontinued')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- Supply Chain / Procurement
CREATE TABLE IF NOT EXISTS supply_chain (
    order_id TEXT PRIMARY KEY,
    item_id INTEGER NOT NULL,
    vendor_name TEXT NOT NULL,
    order_date DATE NOT NULL,
    delivery_date DATE,
    quantity_ordered INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_cost REAL NOT NULL,
    order_status TEXT DEFAULT 'pending' CHECK (order_status IN ('pending', 'confirmed', 'shipped', 'delivered', 'cancelled')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_id) REFERENCES inventory(inventory_id)
);

-- ============================================================================
-- PART 10: COMPLIANCE & AUDIT
-- ============================================================================

-- HIPAA Access Logs (audit trail for all PHI/PII access)
CREATE TABLE IF NOT EXISTS hipaa_access_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    patient_id TEXT,
    record_type TEXT CHECK (record_type IN ('Medical Record', 'Appointment', 'Prescription', 'Lab Result', 'Billing', 'Insurance', 'PII')),
    access_type TEXT CHECK (access_type IN ('view', 'edit', 'delete', 'export', 'create')),
    access_date DATE DEFAULT CURRENT_DATE,
    access_time TIME DEFAULT CURRENT_TIME,
    ip_address TEXT,
    reason_for_access TEXT,
    outcome TEXT CHECK (outcome IN ('success', 'denied', 'error')),
    denial_reason TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES employees(employee_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
);

-- Compliance Audits
CREATE TABLE IF NOT EXISTS compliance_audits (
    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
    audit_date DATE NOT NULL,
    audit_type TEXT CHECK (audit_type IN ('HIPAA', 'Financial', 'Operational', 'Security', 'Quality')),
    department_id INTEGER,
    auditor_id TEXT NOT NULL,
    scope TEXT,
    findings TEXT,
    action_items TEXT,
    risk_level TEXT CHECK (risk_level IN ('low', 'medium', 'high', 'critical')),
    remediation_status TEXT DEFAULT 'pending' CHECK (remediation_status IN ('pending', 'in_progress', 'completed', 'deferred')),
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    FOREIGN KEY (auditor_id) REFERENCES employees(employee_id)
);

-- Incident Reports
CREATE TABLE IF NOT EXISTS incident_reports (
    incident_id TEXT PRIMARY KEY,
    report_date DATE DEFAULT CURRENT_DATE,
    reported_by_id TEXT NOT NULL,
    department_id INTEGER,
    incident_type TEXT CHECK (incident_type IN ('Medical Error', 'Security Breach', 'Data Loss', 'Patient Safety', 'Employee Injury', 'Other')),
    severity TEXT CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    description TEXT NOT NULL,
    affected_parties TEXT,
    immediate_actions_taken TEXT,
    root_cause_analysis TEXT,
    resolution TEXT,
    resolution_date DATE,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'investigating', 'resolved', 'closed')),
    hipaa_breach BOOLEAN DEFAULT 0,
    breach_notification_required BOOLEAN DEFAULT 0,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reported_by_id) REFERENCES employees(employee_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- Regulatory Documents
CREATE TABLE IF NOT EXISTS regulatory_documents (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_name TEXT NOT NULL,
    doc_type TEXT CHECK (doc_type IN ('License', 'Permit', 'Certification', 'Accreditation', 'Agreement')),
    issuing_authority TEXT,
    issue_date DATE,
    expiration_date DATE,
    status TEXT DEFAULT 'active',
    renewal_due_date DATE,
    file_path TEXT,
    department_id INTEGER,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- ============================================================================
-- PART 11: FINANCE & BUDGETING
-- ============================================================================

-- Budget Allocation
CREATE TABLE IF NOT EXISTS budget_allocation (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT,
    department_id INTEGER NOT NULL,
    fiscal_year INTEGER NOT NULL,
    total_budget REAL NOT NULL,
    allocated_budget REAL NOT NULL,
    spent_budget REAL DEFAULT 0,
    remaining_budget REAL,
    category TEXT CHECK (category IN ('Salary', 'Equipment', 'Supplies', 'Training', 'Other')),
    status TEXT DEFAULT 'active',
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    UNIQUE(department_id, fiscal_year, category)
);

-- Expense Reports
CREATE TABLE IF NOT EXISTS expense_reports (
    expense_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    department_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    total_amount REAL NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected', 'reimbursed')),
    approved_by TEXT,
    approved_date DATE,
    reimbursement_date DATE,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES employees(employee_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id),
    FOREIGN KEY (approved_by) REFERENCES employees(employee_id)
);

-- Revenue Streams
CREATE TABLE IF NOT EXISTS revenue_streams (
    revenue_id INTEGER PRIMARY KEY AUTOINCREMENT,
    revenue_source TEXT NOT NULL CHECK (revenue_source IN ('Insurance', 'Patient Payments', 'Grants', 'Partnerships', 'Other')),
    amount REAL NOT NULL,
    transaction_date DATE DEFAULT CURRENT_DATE,
    fiscal_year INTEGER,
    department_id INTEGER,
    description TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- Accounts Payable (vendor invoices)
CREATE TABLE IF NOT EXISTS accounts_payable (
    invoice_id TEXT PRIMARY KEY,
    vendor_name TEXT NOT NULL,
    invoice_date DATE NOT NULL,
    due_date DATE NOT NULL,
    invoice_amount REAL NOT NULL,
    department_id INTEGER,
    description TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'paid', 'disputed')),
    paid_date DATE,
    payment_method TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- ============================================================================
-- PART 12: CONTRACTS & AGREEMENTS
-- ============================================================================

-- Contracts
CREATE TABLE IF NOT EXISTS contracts (
    contract_id TEXT PRIMARY KEY,
    contract_type TEXT CHECK (contract_type IN ('Vendor', 'Service', 'Employment', 'Patient', 'Partnership', 'License')),
    party_name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    value REAL,
    description TEXT,
    contract_terms TEXT,
    department_id INTEGER,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'expired', 'terminated', 'pending')),
    renewal_date DATE,
    document_path TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- ============================================================================
-- PART 13: ANALYTICS & REPORTING
-- ============================================================================

-- Operational Metrics
CREATE TABLE IF NOT EXISTS operational_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE DEFAULT CURRENT_DATE,
    metric_type TEXT CHECK (metric_type IN ('Wait Time', 'Patient Throughput', 'Staff Utilization', 'Revenue', 'Quality Score', 'Other')),
    location_id INTEGER,
    department_id INTEGER,
    metric_value REAL,
    metric_unit TEXT,
    benchmark_value REAL,
    variance REAL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    FOREIGN KEY (department_id) REFERENCES departments(department_id)
);

-- ============================================================================
-- PART 14: INDEXES FOR PERFORMANCE
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department_id);
CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
CREATE INDEX IF NOT EXISTS idx_employees_manager ON employees(manager_id);
CREATE INDEX IF NOT EXISTS idx_patients_location ON patients(assigned_location_id);
CREATE INDEX IF NOT EXISTS idx_appointments_patient ON appointments(patient_id);
CREATE INDEX IF NOT EXISTS idx_appointments_doctor ON appointments(doctor_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(appointment_date);
CREATE INDEX IF NOT EXISTS idx_medical_records_patient ON medical_records(patient_id);
CREATE INDEX IF NOT EXISTS idx_medical_records_date ON medical_records(record_date);
CREATE INDEX IF NOT EXISTS idx_prescriptions_patient ON prescriptions(patient_id);
CREATE INDEX IF NOT EXISTS idx_billing_patient ON billing(patient_id);
CREATE INDEX IF NOT EXISTS idx_billing_status ON billing(status);
CREATE INDEX IF NOT EXISTS idx_hipaa_logs_patient ON hipaa_access_logs(patient_id);
CREATE INDEX IF NOT EXISTS idx_hipaa_logs_user ON hipaa_access_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_hipaa_logs_date ON hipaa_access_logs(access_date);
CREATE INDEX IF NOT EXISTS idx_leave_requests_employee ON leave_requests(employee_id);
CREATE INDEX IF NOT EXISTS idx_leave_requests_status ON leave_requests(status);
CREATE INDEX IF NOT EXISTS idx_certifications_employee ON certifications(employee_id);
CREATE INDEX IF NOT EXISTS idx_certifications_expiry ON certifications(expiration_date);

-- ============================================================================
-- SUMMARY: Total Tables = 56
-- ============================================================================
-- Organization: 6 tables
-- Employees & Staffing: 6 tables
-- Payroll & Compensation: 3 tables
-- Leave & Time Off: 3 tables
-- Patients: 5 tables
-- Clinical Operations: 5 tables
-- Billing & Revenue: 2 tables
-- HR & Training: 2 tables
-- IT & Operations: 4 tables
-- Compliance & Audit: 4 tables
-- Finance & Budgeting: 3 tables
-- Contracts: 1 table
-- Analytics: 1 table
-- ============================================================================
