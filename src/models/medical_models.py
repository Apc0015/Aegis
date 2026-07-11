# ============================================================================
# SQLAlchemy ORM Models for Medical Company Database
# File: src/models/medical_models.py
# ============================================================================

from datetime import datetime, date
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime, Text, Boolean, ForeignKey, CheckConstraint, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import func

Base = declarative_base()

# ============================================================================
# ORGANIZATION STRUCTURE
# ============================================================================

class Location(Base):
    __tablename__ = 'locations'
    
    location_id = Column(Integer, primary_key=True, autoincrement=True)
    location_name = Column(String(255), nullable=False, unique=True)
    address = Column(String(255), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(50), nullable=False)
    zip_code = Column(String(10), nullable=False)
    phone = Column(String(20))
    manager_id = Column(String(50), ForeignKey('employees.employee_id'))
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    departments = relationship('Department', back_populates='location')
    employees = relationship('Employee', back_populates='location', foreign_keys='Employee.location_id')
    facilities = relationship('MedicalFacility', back_populates='location')


class Department(Base):
    __tablename__ = 'departments'
    
    department_id = Column(Integer, primary_key=True, autoincrement=True)
    department_name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    head_id = Column(String(50), ForeignKey('employees.employee_id'))
    location_id = Column(Integer, ForeignKey('locations.location_id'))
    budget = Column(Float)
    fiscal_year = Column(Integer, default=2026)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    location = relationship('Location', back_populates='departments')
    teams = relationship('Team', back_populates='department', foreign_keys='Team.department_id')
    employees = relationship('Employee', back_populates='department', foreign_keys='Employee.department_id')


class Team(Base):
    __tablename__ = 'teams'
    
    team_id = Column(Integer, primary_key=True, autoincrement=True)
    team_name = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.department_id'), nullable=False)
    team_lead_id = Column(String(50), ForeignKey('employees.employee_id'))
    location_id = Column(Integer, ForeignKey('locations.location_id'))
    budget = Column(Float)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    department = relationship('Department', back_populates='teams', foreign_keys=[department_id])
    employees = relationship('Employee', back_populates='team', foreign_keys='Employee.team_id')


# ============================================================================
# EMPLOYEES & STAFFING
# ============================================================================

class Employee(Base):
    __tablename__ = 'employees'
    
    employee_id = Column(String(50), primary_key=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), nullable=False, unique=True)
    phone = Column(String(20))
    department_id = Column(Integer, ForeignKey('departments.department_id'), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.team_id'))
    job_title = Column(String(100), nullable=False)
    employment_type = Column(String(50), nullable=False)  # FT, PT, Contract, Temporary
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    manager_id = Column(String(50), ForeignKey('employees.employee_id'))
    salary = Column(Float)
    salary_grade = Column(String(50))
    location_id = Column(Integer, ForeignKey('locations.location_id'))
    status = Column(String(50), default='active')  # active, inactive, on_leave, terminated
    ssn_encrypted = Column(Text)
    date_of_birth = Column(Date)
    gender = Column(String(10))
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        CheckConstraint("employment_type IN ('FT', 'PT', 'Contract', 'Temporary')"),
        CheckConstraint("status IN ('active', 'inactive', 'on_leave', 'terminated')"),
    )
    
    department = relationship('Department', back_populates='employees', foreign_keys=[department_id])
    team = relationship('Team', back_populates='employees', foreign_keys=[team_id])
    location = relationship('Location', back_populates='employees', foreign_keys=[location_id])
    certifications = relationship('Certification', back_populates='employee', cascade='all, delete-orphan')
    payroll_records = relationship('Payroll', back_populates='employee', cascade='all, delete-orphan')
    leave_requests = relationship('LeaveRequest', back_populates='employee', foreign_keys='LeaveRequest.employee_id')
    benefits = relationship('EmployeeBenefit', back_populates='employee', cascade='all, delete-orphan')


class Certification(Base):
    __tablename__ = 'certifications'
    
    cert_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    certification_name = Column(String(255), nullable=False)
    certification_number = Column(String(100))
    issuing_authority = Column(String(255))
    issue_date = Column(Date, nullable=False)
    expiration_date = Column(Date)
    status = Column(String(50), default='active')  # active, expired, pending, suspended
    is_medical_license = Column(Boolean, default=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employee = relationship('Employee', back_populates='certifications')


class EmployeeRole(Base):
    __tablename__ = 'employee_roles'
    
    role_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    role_name = Column(String(100), nullable=False)
    role_description = Column(Text)
    department_id = Column(Integer, ForeignKey('departments.department_id'), nullable=False)
    is_primary = Column(Boolean, default=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    created_date = Column(DateTime, default=datetime.utcnow)


class MedicalSpecialty(Base):
    __tablename__ = 'medical_specialties'
    
    specialty_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    specialty_name = Column(String(255), nullable=False)
    board_certified = Column(Boolean, default=False)
    years_of_experience = Column(Integer)
    created_date = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# PAYROLL & COMPENSATION
# ============================================================================

class Payroll(Base):
    __tablename__ = 'payroll'
    
    payroll_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    pay_period_start = Column(Date, nullable=False)
    pay_period_end = Column(Date, nullable=False)
    gross_salary = Column(Float, nullable=False)
    federal_tax = Column(Float)
    state_tax = Column(Float)
    social_security = Column(Float)
    medicare = Column(Float)
    health_insurance_deduction = Column(Float)
    other_deductions = Column(Float)
    net_pay = Column(Float, nullable=False)
    payment_date = Column(Date)
    payment_method = Column(String(50))  # Direct Deposit, Check
    status = Column(String(50), default='pending')  # pending, processed, cancelled
    created_date = Column(DateTime, default=datetime.utcnow)
    
    employee = relationship('Employee', back_populates='payroll_records')


class EmployeeBenefit(Base):
    __tablename__ = 'employee_benefits'
    
    enrollment_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    benefit_name = Column(String(100), nullable=False)
    benefit_type = Column(String(50))  # Health Insurance, 401k, FSA, HSA, Life Insurance, Disability, Other
    provider = Column(String(255))
    enrollment_date = Column(Date, nullable=False)
    status = Column(String(50), default='active')  # active, inactive, pending, cancelled
    coverage_level = Column(String(100))
    premium_amount = Column(Float)
    employer_contribution = Column(Float)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    employee = relationship('Employee', back_populates='benefits')


# ============================================================================
# LEAVE & TIME OFF
# ============================================================================

class LeavePolicy(Base):
    __tablename__ = 'leave_policies'
    
    policy_id = Column(Integer, primary_key=True, autoincrement=True)
    policy_name = Column(String(100), nullable=False)
    leave_type = Column(String(50), nullable=False)  # Vacation, Sick, Medical, Maternity, etc.
    days_per_year = Column(Integer)
    carry_over_max = Column(Integer)
    description = Column(Text)
    effective_date = Column(Date)
    created_date = Column(DateTime, default=datetime.utcnow)


class LeaveRequest(Base):
    __tablename__ = 'leave_requests'
    
    request_id = Column(String(50), primary_key=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    leave_type = Column(String(50), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_requested = Column(Integer, nullable=False)
    status = Column(String(50), default='pending')  # pending, approved, rejected, cancelled
    approved_by = Column(String(50), ForeignKey('employees.employee_id'))
    submitted_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime)
    rejection_reason = Column(Text)
    notes = Column(Text)
    
    employee = relationship('Employee', back_populates='leave_requests', foreign_keys=[employee_id])


# ============================================================================
# PATIENT MANAGEMENT
# ============================================================================

class Patient(Base):
    __tablename__ = 'patients'
    
    patient_id = Column(String(50), primary_key=True)
    patient_age_group = Column(String(20))  # 0-18, 19-30, 31-50, 51-65, 65+
    gender = Column(String(10))  # M, F, Other, Unknown
    blood_type = Column(String(10))
    medical_conditions = Column(Text)  # Comma-separated
    medications_summary = Column(Text)
    patient_status = Column(String(50), default='active')  # active, inactive, deceased, transferred
    primary_care_doctor_id = Column(String(50), ForeignKey('employees.employee_id'))
    assigned_location_id = Column(Integer, ForeignKey('locations.location_id'))
    created_date = Column(DateTime, default=datetime.utcnow)
    last_visit_date = Column(Date)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    appointments = relationship('Appointment', back_populates='patient')
    medical_records = relationship('MedicalRecord', back_populates='patient')
    prescriptions = relationship('Prescription', back_populates='patient')
    lab_results = relationship('LabResult', back_populates='patient')


class PatientPII(Base):
    __tablename__ = 'patient_pii'
    
    pii_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False, unique=True)
    first_name_encrypted = Column(Text, nullable=False)
    last_name_encrypted = Column(Text, nullable=False)
    ssn_encrypted = Column(Text, unique=True)
    date_of_birth_encrypted = Column(Date)
    phone_encrypted = Column(Text)
    email_encrypted = Column(Text)
    address_encrypted = Column(Text)
    city_encrypted = Column(Text)
    state_encrypted = Column(Text)
    zip_code_encrypted = Column(Text)
    emergency_contact_encrypted = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class InsuranceInfo(Base):
    __tablename__ = 'insurance_info'
    
    insurance_id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    insurance_provider = Column(String(255), nullable=False)
    policy_number_encrypted = Column(Text)
    group_number = Column(String(50))
    member_id_encrypted = Column(Text)
    coverage_start_date = Column(Date)
    coverage_end_date = Column(Date)
    coverage_type = Column(String(50))  # Individual, Family, Group
    co_pay = Column(Float)
    deductible = Column(Float)
    max_out_of_pocket = Column(Float)
    is_primary = Column(Boolean, default=True)
    status = Column(String(50), default='active')
    created_date = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# CLINICAL OPERATIONS
# ============================================================================

class Appointment(Base):
    __tablename__ = 'appointments'
    
    appointment_id = Column(String(50), primary_key=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    doctor_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    appointment_date = Column(Date, nullable=False)
    appointment_time = Column(String(10), nullable=False)
    duration_minutes = Column(Integer, default=30)
    appointment_type = Column(String(50))  # Routine, Follow-up, Consultation, Procedure, Urgent
    status = Column(String(50), default='scheduled')  # scheduled, completed, cancelled, no-show, rescheduled
    location_id = Column(Integer, ForeignKey('locations.location_id'))
    reason = Column(Text)
    notes = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship('Patient', back_populates='appointments')
    medical_records = relationship('MedicalRecord', back_populates='appointment')
    billings = relationship('Billing', back_populates='appointment')


class MedicalRecord(Base):
    __tablename__ = 'medical_records'
    
    record_id = Column(String(50), primary_key=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    record_date = Column(Date, nullable=False)
    doctor_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    appointment_id = Column(String(50), ForeignKey('appointments.appointment_id'))
    diagnosis = Column(Text)
    icd_codes = Column(Text)  # International Classification of Diseases
    treatment_plan = Column(Text)
    medications_prescribed = Column(Text)
    notes = Column(Text)
    is_confidential = Column(Boolean, default=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    updated_date = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    patient = relationship('Patient', back_populates='medical_records')
    appointment = relationship('Appointment', back_populates='medical_records')


class Prescription(Base):
    __tablename__ = 'prescriptions'
    
    prescription_id = Column(String(50), primary_key=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    doctor_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    medication_name = Column(String(255), nullable=False)
    ndc_code = Column(String(50))  # National Drug Code
    strength = Column(String(50))
    dosage = Column(String(100), nullable=False)
    frequency = Column(String(100), nullable=False)
    route = Column(String(50))  # Oral, Injection, Inhalation, Topical, Other
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    refills_allowed = Column(Integer, default=0)
    refills_remaining = Column(Integer)
    status = Column(String(50), default='active')  # active, inactive, completed, discontinued
    created_date = Column(DateTime, default=datetime.utcnow)
    
    patient = relationship('Patient', back_populates='prescriptions')


class LabResult(Base):
    __tablename__ = 'lab_results'
    
    result_id = Column(String(50), primary_key=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    test_date = Column(Date, nullable=False)
    test_name = Column(String(255), nullable=False)
    test_code = Column(String(50))  # LOINC code
    ordered_by_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    result_value = Column(Text)
    unit = Column(String(50))
    reference_range = Column(String(100))
    abnormal_flag = Column(String(50))  # Normal, Abnormal, Critical
    status = Column(String(50), default='pending')  # pending, received, reviewed, reported
    notes = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    patient = relationship('Patient', back_populates='lab_results')


class MedicalFacility(Base):
    __tablename__ = 'medical_facilities'
    
    facility_id = Column(Integer, primary_key=True, autoincrement=True)
    facility_name = Column(String(255), nullable=False)
    facility_type = Column(String(50))  # Clinic, Hospital, Lab, Imaging Center, Pharmacy
    location_id = Column(Integer, ForeignKey('locations.location_id'), nullable=False)
    capacity = Column(Integer)
    operating_hours = Column(String(255))
    is_primary = Column(Boolean, default=False)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    location = relationship('Location', back_populates='facilities')


# ============================================================================
# BILLING & REVENUE
# ============================================================================

class Billing(Base):
    __tablename__ = 'billing'
    
    billing_id = Column(String(50), primary_key=True)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    appointment_id = Column(String(50), ForeignKey('appointments.appointment_id'))
    billing_date = Column(Date, nullable=False)
    service_code = Column(String(50))  # CPT code
    service_description = Column(String(255))
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    insurance_coverage = Column(Float, default=0)
    patient_responsibility = Column(Float)
    status = Column(String(50), default='open')  # open, partial, paid, written_off, pending
    due_date = Column(Date)
    paid_date = Column(Date)
    payment_method = Column(String(50))
    notes = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    patient = relationship('Patient')
    appointment = relationship('Appointment', back_populates='billings')
    claims = relationship('ClaimsProcessing', back_populates='billing')


class ClaimsProcessing(Base):
    __tablename__ = 'claims_processing'
    
    claim_id = Column(String(50), primary_key=True)
    billing_id = Column(String(50), ForeignKey('billing.billing_id'), nullable=False)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'), nullable=False)
    insurance_id = Column(Integer, ForeignKey('insurance_info.insurance_id'), nullable=False)
    claim_date = Column(Date, nullable=False)
    submitted_date = Column(Date)
    claim_amount = Column(Float, nullable=False)
    approved_amount = Column(Float)
    denied_amount = Column(Float)
    claim_status = Column(String(50), default='submitted')  # submitted, acknowledged, processing, approved, etc.
    denial_reason = Column(Text)
    appeal_count = Column(Integer, default=0)
    notes = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    billing = relationship('Billing', back_populates='claims')


# ============================================================================
# HR & TRAINING
# ============================================================================

class TrainingRecord(Base):
    __tablename__ = 'training_records'
    
    training_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    training_name = Column(String(255), nullable=False)
    training_type = Column(String(50))  # HIPAA, Safety, Compliance, Professional Dev, Mandatory, Other
    training_date = Column(Date, nullable=False)
    completion_date = Column(Date)
    certification_issued = Column(Boolean, default=False)
    certification_expiry = Column(Date)
    status = Column(String(50), default='pending')  # pending, in_progress, completed, failed
    score = Column(Integer)
    provider = Column(String(255))
    notes = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)


class PerformanceReview(Base):
    __tablename__ = 'performance_reviews'
    
    review_id = Column(Integer, primary_key=True, autoincrement=True)
    employee_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    reviewer_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    review_date = Column(Date, nullable=False)
    review_period_start = Column(Date)
    review_period_end = Column(Date)
    performance_rating = Column(String(50))  # Exceeds, Meets, Below, Needs Improvement
    overall_score = Column(Integer)  # 1-5
    strengths = Column(Text)
    areas_for_improvement = Column(Text)
    goals_for_next_period = Column(Text)
    comments = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# IT & OPERATIONS
# ============================================================================

class ITAsset(Base):
    __tablename__ = 'it_assets'
    
    asset_id = Column(Integer, primary_key=True, autoincrement=True)
    asset_name = Column(String(255), nullable=False)
    asset_type = Column(String(50))  # Server, Workstation, Laptop, Mobile, Network, Software, License
    asset_tag = Column(String(100), unique=True)
    serial_number = Column(String(100))
    assigned_to_id = Column(String(50), ForeignKey('employees.employee_id'))
    location_id = Column(Integer, ForeignKey('locations.location_id'))
    purchase_date = Column(Date)
    warranty_expiry = Column(Date)
    maintenance_contract = Column(Boolean, default=False)
    status = Column(String(50), default='active')  # active, inactive, retired, for_repair
    created_date = Column(DateTime, default=datetime.utcnow)


class Inventory(Base):
    __tablename__ = 'inventory'
    
    inventory_id = Column(Integer, primary_key=True, autoincrement=True)
    item_name = Column(String(255), nullable=False)
    item_code = Column(String(100), unique=True)
    item_type = Column(String(50))  # Medical Supply, Equipment, Medication, Office Supply
    location_id = Column(Integer, ForeignKey('locations.location_id'), nullable=False)
    quantity_on_hand = Column(Integer, nullable=False)
    minimum_quantity = Column(Integer)
    reorder_quantity = Column(Integer)
    unit_cost = Column(Float)
    last_count_date = Column(Date)
    status = Column(String(50), default='in_stock')  # in_stock, low_stock, out_of_stock, discontinued
    created_date = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# COMPLIANCE & AUDIT
# ============================================================================

class HIPAAAccessLog(Base):
    __tablename__ = 'hipaa_access_logs'
    
    log_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    patient_id = Column(String(50), ForeignKey('patients.patient_id'))
    record_type = Column(String(50))  # Medical Record, Appointment, Prescription, Lab Result, Billing, Insurance, PII
    access_type = Column(String(50))  # view, edit, delete, export, create
    access_date = Column(Date, default=date.today)
    access_time = Column(String(10))
    ip_address = Column(String(50))
    reason_for_access = Column(Text)
    outcome = Column(String(50))  # success, denied, error
    denial_reason = Column(Text)
    created_date = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_hipaa_logs_patient', 'patient_id'),
        Index('idx_hipaa_logs_user', 'user_id'),
        Index('idx_hipaa_logs_date', 'access_date'),
    )


class ComplianceAudit(Base):
    __tablename__ = 'compliance_audits'
    
    audit_id = Column(Integer, primary_key=True, autoincrement=True)
    audit_date = Column(Date, nullable=False)
    audit_type = Column(String(50))  # HIPAA, Financial, Operational, Security, Quality
    department_id = Column(Integer, ForeignKey('departments.department_id'))
    auditor_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    scope = Column(Text)
    findings = Column(Text)
    action_items = Column(Text)
    risk_level = Column(String(50))  # low, medium, high, critical
    remediation_status = Column(String(50), default='pending')  # pending, in_progress, completed, deferred
    created_date = Column(DateTime, default=datetime.utcnow)


class IncidentReport(Base):
    __tablename__ = 'incident_reports'
    
    incident_id = Column(String(50), primary_key=True)
    report_date = Column(Date, default=date.today)
    reported_by_id = Column(String(50), ForeignKey('employees.employee_id'), nullable=False)
    department_id = Column(Integer, ForeignKey('departments.department_id'))
    incident_type = Column(String(50))  # Medical Error, Security Breach, Data Loss, Patient Safety, Employee Injury, Other
    severity = Column(String(50))  # low, medium, high, critical
    description = Column(Text, nullable=False)
    affected_parties = Column(Text)
    immediate_actions_taken = Column(Text)
    root_cause_analysis = Column(Text)
    resolution = Column(Text)
    resolution_date = Column(Date)
    status = Column(String(50), default='open')  # open, investigating, resolved, closed
    hipaa_breach = Column(Boolean, default=False)
    breach_notification_required = Column(Boolean, default=False)
    created_date = Column(DateTime, default=datetime.utcnow)


# ============================================================================
# DATABASE CONNECTION SETUP
# ============================================================================

def create_db_session(database_url: str = 'sqlite:////Users/apc/Study/Projects/Working/Aegis/data/medical_company.db'):
    """
    Create a database session for use with SQLAlchemy ORM
    
    Args:
        database_url: SQLite database path (default: medical_company.db)
    
    Returns:
        Session: SQLAlchemy session object
    """
    engine = create_engine(database_url, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


if __name__ == '__main__':
    # Example usage
    session = create_db_session()
    
    # Query example
    employees = session.query(Employee).filter_by(status='active').limit(5).all()
    print(f"Active employees: {len(employees)}")
    
    session.close()
