#!/usr/bin/env python3
# ============================================================================
# Data Seeding Script for Medical Company Database
# File: scripts/seed_medical_database.py
# Purpose: Populate database with 500 employees and realistic sample data
# ============================================================================

import os
import sys
import random
from datetime import datetime, date, timedelta
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.medical_models import (
    create_db_session, Base, Location, Department, Team, Employee,
    Certification, EmployeeBenefit, LeaveRequest, Patient, PatientPII,
    InsuranceInfo, Appointment, MedicalRecord, Prescription, LabResult,
    Billing, HIPAAAccessLog, ComplianceAudit, IncidentReport, TrainingRecord,
    PerformanceReview, MedicalFacility, Inventory, ITAsset
)
from sqlalchemy import create_engine

# ============================================================================
# SAMPLE DATA GENERATORS
# ============================================================================

# Department names and descriptions
DEPARTMENTS = [
    ('Customer_Success', 'Patient support and customer success', 60),
    ('Engineering', 'IT and systems engineering', 40),
    ('Finance', 'Financial planning and accounting', 35),
    ('HR', 'Human resources and recruiting', 30),
    ('IT', 'Information technology and infrastructure', 45),
    ('Legal', 'Legal compliance and contracts', 20),
    ('Marketing', 'Marketing and business development', 35),
    ('Operations', 'Operations and facility management', 50),
    ('Product', 'Product development and medical informatics', 50),
    ('Sales', 'Sales and business partnerships', 40),
]

LOCATIONS = [
    ('New York HQ', '123 Medical Plaza', 'New York', 'NY', '10001'),
    ('Boston Clinic', '456 Healthcare Ave', 'Boston', 'MA', '02101'),
    ('Atlanta Facility', '789 Medical Center', 'Atlanta', 'GA', '30303'),
    ('Chicago Office', '321 Health Blvd', 'Chicago', 'IL', '60601'),
    ('San Francisco Lab', '654 Tech Drive', 'San Francisco', 'CA', '94102'),
]

FIRST_NAMES = [
    'James', 'Mary', 'Robert', 'Patricia', 'Michael', 'Jennifer', 'William', 'Linda',
    'David', 'Barbara', 'Richard', 'Elizabeth', 'Joseph', 'Susan', 'Thomas', 'Jessica',
    'Charles', 'Sarah', 'Christopher', 'Karen', 'Daniel', 'Lisa', 'Matthew', 'Nancy',
    'Anthony', 'Betty', 'Mark', 'Margaret', 'Donald', 'Sandra', 'Steven', 'Ashley',
]

LAST_NAMES = [
    'Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia', 'Miller', 'Davis',
    'Rodriguez', 'Martinez', 'Hernandez', 'Lopez', 'Gonzalez', 'Wilson', 'Anderson',
    'Thomas', 'Taylor', 'Moore', 'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson',
    'White', 'Harris', 'Sanchez', 'Clark', 'Ramirez', 'Lewis', 'Robinson',
]

JOB_TITLES_BY_DEPT = {
    'Customer_Success': ['CS Manager', 'Support Specialist', 'Account Manager', 'CS Lead', 'Support Engineer'],
    'Engineering': ['Software Engineer', 'DevOps Engineer', 'Systems Architect', 'Engineering Manager', 'Tech Lead'],
    'Finance': ['Finance Manager', 'Accountant', 'Financial Analyst', 'CFO', 'Billing Specialist'],
    'HR': ['HR Manager', 'Recruiter', 'HR Specialist', 'HR Director', 'Onboarding Coordinator'],
    'IT': ['IT Manager', 'Network Administrator', 'IT Support', 'Security Engineer', 'Infrastructure Specialist'],
    'Legal': ['Attorney', 'Legal Counsel', 'Compliance Officer', 'Contract Manager', 'Legal Assistant'],
    'Marketing': ['Marketing Manager', 'Marketing Specialist', 'Content Creator', 'Digital Marketing', 'Brand Manager'],
    'Operations': ['Operations Manager', 'Facility Manager', 'Operations Specialist', 'Supply Chain', 'Logistics Manager'],
    'Product': ['Product Manager', 'Medical Informatics', 'Product Designer', 'Product Lead', 'UX Researcher'],
    'Sales': ['Sales Manager', 'Account Executive', 'Sales Rep', 'Business Development', 'Territory Manager'],
}

MEDICAL_TITLES = [
    'MD - Internal Medicine', 'MD - Surgery', 'RN - Registered Nurse', 'LPN - Licensed Practical Nurse',
    'PA - Physician Assistant', 'NP - Nurse Practitioner', 'Specialist - Cardiology', 'Specialist - Pediatrics',
    'Clinical Director', 'Medical Director', 'Surgeon', 'Psychiatrist'
]

CERTIFICATIONS = [
    ('MD License', 'State Medical Board', 'Medical License'),
    ('RN License', 'State Nursing Board', 'Nursing License'),
    ('HIPAA Certification', 'HHS', 'Compliance'),
    ('CPR Certification', 'American Red Cross', 'Safety'),
    ('IT Security+', 'CompTIA', 'IT Certification'),
    ('CPA License', 'State Board of Accountancy', 'Financial'),
    ('MBA Degree', 'University', 'Professional Degree'),
]

MEDICAL_CONDITIONS = [
    'Hypertension', 'Diabetes Type 2', 'Asthma', 'Hyperlipidemia', 'Arthritis',
    'Depression', 'Anxiety', 'COPD', 'Coronary Artery Disease', 'Atrial Fibrillation',
    'Obesity', 'Thyroid Disorder', 'Migraine', 'Sleep Apnea', 'Acid Reflux'
]

MEDICATIONS = [
    'Metformin', 'Lisinopril', 'Atorvastatin', 'Albuterol', 'Ibuprofen',
    'Sertraline', 'Omeprazole', 'Levothyroxine', 'Warfarin', 'Aspirin',
    'Amlodipine', 'Hydrochlorothiazide', 'Metoprolol', 'Simvastatin', 'Amoxicillin'
]

BLOOD_TYPES = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-']

INSURANCE_PROVIDERS = [
    'United Healthcare', 'Aetna', 'Humana', 'Cigna', 'Blue Cross Blue Shield',
    'Anthem', 'Medicare', 'Medicaid', 'Tricare', 'Veterans Health'
]

# ============================================================================
# MAIN SEEDING FUNCTION
# ============================================================================

def seed_database():
    """
    Seed the medical company database with realistic sample data
    """
    print("=" * 80)
    print("AEGIS — SAMPLE DATASET SEEDING")
    print("Fictional 500-employee healthcare company · demo / evaluation data only")
    print("=" * 80)
    
    # Create session
    session = create_db_session()
    
    try:
        # ====================================================================
        # 1. SEED LOCATIONS
        # ====================================================================
        print("\n[1/8] Seeding Locations...")
        locations = []
        for loc_name, address, city, state, zip_code in LOCATIONS:
            location = Location(
                location_name=loc_name,
                address=address,
                city=city,
                state=state,
                zip_code=zip_code,
                phone=f"1-555-{random.randint(100,999)}-{random.randint(1000,9999)}"
            )
            locations.append(location)
            session.add(location)
        session.commit()
        print(f"✓ Created {len(locations)} locations")
        
        # ====================================================================
        # 2. SEED DEPARTMENTS
        # ====================================================================
        print("\n[2/8] Seeding Departments...")
        departments = {}
        for dept_name, description, _ in DEPARTMENTS:
            location = random.choice(locations)
            department = Department(
                department_name=dept_name,
                description=description,
                location_id=location.location_id,
                budget=random.randint(500000, 3000000),
                fiscal_year=2026
            )
            departments[dept_name] = department
            session.add(department)
        session.commit()
        print(f"✓ Created {len(departments)} departments")
        
        # ====================================================================
        # 3. SEED TEAMS
        # ====================================================================
        print("\n[3/8] Seeding Teams...")
        teams_by_dept = {}
        for dept_name, _, expected_count in DEPARTMENTS:
            dept = departments[dept_name]
            num_teams = max(2, expected_count // 15)  # 2-4 teams per department
            teams_by_dept[dept_name] = []
            for i in range(num_teams):
                team = Team(
                    team_name=f"{dept_name} Team {i+1}",
                    department_id=dept.department_id,
                    location_id=dept.location_id,
                    budget=random.randint(100000, 500000)
                )
                teams_by_dept[dept_name].append(team)
                session.add(team)
        session.commit()
        total_teams = sum(len(teams) for teams in teams_by_dept.values())
        print(f"✓ Created {total_teams} teams")
        
        # ====================================================================
        # 4. SEED EMPLOYEES (500 total)
        # ====================================================================
        print("\n[4/8] Seeding Employees (500 total)...")
        employees = {}
        employee_count = 0
        used_emails = set()
        
        for dept_name, _, expected_count in DEPARTMENTS:
            dept = departments[dept_name]
            teams = teams_by_dept[dept_name]
            
            for i in range(expected_count):
                first_name = random.choice(FIRST_NAMES)
                last_name = random.choice(LAST_NAMES)
                employee_id = f"EMP{2000 + employee_count:06d}"
                
                # Generate unique email
                email = f"{first_name.lower()}.{last_name.lower()}@medicalco.com"
                counter = 1
                while email in used_emails:
                    email = f"{first_name.lower()}.{last_name.lower()}{counter}@medicalco.com"
                    counter += 1
                used_emails.add(email)
                
                # Determine job title and whether it's a medical role
                is_medical_staff = dept_name in ['Operations'] and random.random() < 0.3
                if is_medical_staff:
                    job_title = random.choice(MEDICAL_TITLES)
                else:
                    job_title = random.choice(JOB_TITLES_BY_DEPT[dept_name])
                
                employee = Employee(
                    employee_id=employee_id,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    phone=f"1-555-{random.randint(100,999)}-{random.randint(1000,9999)}",
                    department_id=dept.department_id,
                    team_id=random.choice(teams).team_id,
                    job_title=job_title,
                    employment_type=random.choice(['FT', 'PT', 'Contract']),
                    start_date=date.today() - timedelta(days=random.randint(30, 2000)),
                    manager_id=None,  # Set after initial creation
                    salary=random.randint(50000, 250000),
                    salary_grade=random.choice(['A', 'B', 'C', 'D', 'E']),
                    location_id=random.choice(locations).location_id,
                    status='active' if random.random() < 0.95 else 'inactive',
                    date_of_birth=date.today() - timedelta(days=random.randint(10000, 25000)),
                    gender=random.choice(['M', 'F'])
                )
                employees[employee_id] = employee
                session.add(employee)
                employee_count += 1
                
                # Assign managers (20% of employees are managers)
                if random.random() < 0.2 and len(employees) > 1:
                    manager_id = random.choice(list(employees.keys()))
                    if manager_id != employee_id:
                        employee.manager_id = manager_id
        
        session.commit()
        print(f"✓ Created {len(employees)} employees")
        
        # ====================================================================
        # 5. SEED CERTIFICATIONS
        # ====================================================================
        print("\n[5/8] Seeding Certifications...")
        cert_count = 0
        for employee_id, employee in list(employees.items())[:100]:  # First 100 employees
            if random.random() < 0.6:  # 60% have certifications
                num_certs = random.randint(1, 3)
                for _ in range(num_certs):
                    cert_name, authority, _ = random.choice(CERTIFICATIONS)
                    cert = Certification(
                        employee_id=employee_id,
                        certification_name=cert_name,
                        certification_number=f"CERT{random.randint(100000, 999999)}",
                        issuing_authority=authority,
                        issue_date=date.today() - timedelta(days=random.randint(90, 1825)),
                        expiration_date=date.today() + timedelta(days=random.randint(30, 1825)),
                        status=random.choice(['active', 'pending']),
                        is_medical_license='License' in cert_name
                    )
                    session.add(cert)
                    cert_count += 1
        
        session.commit()
        print(f"✓ Created {cert_count} certifications")
        
        # ====================================================================
        # 6. SEED PATIENTS (5000 total)
        # ====================================================================
        print("\n[6/8] Seeding Patients and Medical Data...")
        patients = {}
        patient_count = 0
        
        for i in range(5000):
            patient_id = f"PAT{1000000 + i:07d}"
            patient = Patient(
                patient_id=patient_id,
                patient_age_group=random.choice(['0-18', '19-30', '31-50', '51-65', '65+']),
                gender=random.choice(['M', 'F', 'Other']),
                blood_type=random.choice(BLOOD_TYPES),
                medical_conditions=','.join(random.sample(MEDICAL_CONDITIONS, random.randint(0, 3))),
                medications_summary=','.join(random.sample(MEDICATIONS, random.randint(0, 4))),
                patient_status='active' if random.random() < 0.95 else 'inactive',
                primary_care_doctor_id=random.choice(list(employees.keys())),
                assigned_location_id=random.choice(locations).location_id,
                last_visit_date=date.today() - timedelta(days=random.randint(1, 365))
            )
            patients[patient_id] = patient
            session.add(patient)
            patient_count += 1
            
            # Create PII record
            pii = PatientPII(
                patient_id=patient_id,
                first_name_encrypted=f"ENC_{random.choice(FIRST_NAMES)}",
                last_name_encrypted=f"ENC_{random.choice(LAST_NAMES)}",
                ssn_encrypted=f"ENC_SSN_{random.randint(100000000, 999999999)}",
                date_of_birth_encrypted=date.today() - timedelta(days=random.randint(5000, 35000)),
                phone_encrypted=f"ENC_555_{random.randint(1000000, 9999999)}",
                email_encrypted=f"ENC_EMAIL_{random.randint(1000, 9999)}",
                address_encrypted=f"ENC_ADDR_{random.randint(1000, 9999)}"
            )
            session.add(pii)
            
            # Create insurance info
            if random.random() < 0.9:
                insurance = InsuranceInfo(
                    patient_id=patient_id,
                    insurance_provider=random.choice(INSURANCE_PROVIDERS),
                    policy_number_encrypted=f"ENC_POL_{random.randint(100000000, 999999999)}",
                    group_number=f"GRP{random.randint(10000, 99999)}",
                    coverage_start_date=date.today() - timedelta(days=random.randint(30, 730)),
                    coverage_end_date=date.today() + timedelta(days=random.randint(30, 730)),
                    coverage_type=random.choice(['Individual', 'Family', 'Group']),
                    co_pay=random.choice([10, 20, 30, 50]),
                    deductible=random.randint(500, 5000),
                    max_out_of_pocket=random.randint(3000, 15000),
                    is_primary=True
                )
                session.add(insurance)
        
        session.commit()
        print(f"✓ Created {patient_count} patients with PII and insurance")
        
        # ====================================================================
        # 7. SEED CLINICAL DATA (Appointments, Medical Records, Prescriptions)
        # ====================================================================
        print("\n[7/8] Seeding Clinical Data...")
        appt_count = 0
        record_count = 0
        rx_count = 0
        
        for i, (patient_id, patient) in enumerate(list(patients.items())[:1000]):
            # Create appointments
            num_appts = random.randint(1, 5)
            for j in range(num_appts):
                appt_id = f"APT{i:06d}_{j}"
                doctor_id = random.choice(list(employees.keys()))
                appt = Appointment(
                    appointment_id=appt_id,
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    appointment_date=date.today() - timedelta(days=random.randint(0, 365)),
                    appointment_time=f"{random.randint(8, 17):02d}:{random.randint(0, 59):02d}",
                    appointment_type=random.choice(['Routine', 'Follow-up', 'Consultation', 'Urgent']),
                    status=random.choice(['completed', 'scheduled']),
                    location_id=random.choice(locations).location_id,
                    reason=random.choice(['Annual checkup', 'Follow-up', 'Symptoms', 'Prescription refill'])
                )
                session.add(appt)
                appt_count += 1
                
                # Create medical records
                if appt.status == 'completed':
                    record = MedicalRecord(
                        record_id=f"MED{i:06d}_{j}",
                        patient_id=patient_id,
                        record_date=appt.appointment_date,
                        doctor_id=doctor_id,
                        appointment_id=appt_id,
                        diagnosis=random.choice(['Hypertension', 'Diabetes', 'Asthma', 'Healthy', 'Needs follow-up']),
                        treatment_plan='Continue current regimen' if random.random() < 0.7 else 'Adjust medication',
                        notes='Patient doing well' if random.random() < 0.8 else 'Requires monitoring'
                    )
                    session.add(record)
                    record_count += 1
                    
                    # Create prescriptions
                    if random.random() < 0.6:
                        rx = Prescription(
                            prescription_id=f"RX{i:06d}_{j}",
                            patient_id=patient_id,
                            doctor_id=doctor_id,
                            medication_name=random.choice(MEDICATIONS),
                            dosage=random.choice(['250mg', '500mg', '1000mg', '2.5mg', '5mg', '10mg']),
                            frequency=random.choice(['Once daily', 'Twice daily', 'Three times daily', 'As needed']),
                            start_date=appt.appointment_date,
                            end_date=appt.appointment_date + timedelta(days=random.randint(30, 365)),
                            refills_allowed=random.randint(0, 11),
                            status='active'
                        )
                        session.add(rx)
                        rx_count += 1
        
        session.commit()
        print(f"✓ Created {appt_count} appointments, {record_count} medical records, {rx_count} prescriptions")
        
        # ====================================================================
        # 8. SEED AUDIT & COMPLIANCE DATA
        # ====================================================================
        print("\n[8/8] Seeding Audit and Compliance Data...")
        audit_count = 0
        incident_count = 0
        
        # HIPAA Access Logs
        for i in range(500):
            log = HIPAAAccessLog(
                user_id=random.choice(list(employees.keys())),
                patient_id=random.choice(list(patients.keys())),
                record_type=random.choice(['Medical Record', 'Appointment', 'Prescription', 'Lab Result']),
                access_type=random.choice(['view', 'edit']),
                access_date=date.today() - timedelta(days=random.randint(0, 30)),
                ip_address=f"192.168.{random.randint(1, 255)}.{random.randint(1, 255)}",
                reason_for_access=random.choice(['Patient care', 'Administrative', 'Billing', 'Quality review']),
                outcome='success' if random.random() < 0.98 else 'denied'
            )
            session.add(log)
        
        # Compliance Audits
        for dept_id in departments.values():
            for i in range(random.randint(1, 3)):
                audit = ComplianceAudit(
                    audit_date=date.today() - timedelta(days=random.randint(1, 365)),
                    audit_type=random.choice(['HIPAA', 'Financial', 'Quality']),
                    department_id=dept_id.department_id,
                    auditor_id=random.choice(list(employees.keys())),
                    findings='No significant findings' if random.random() < 0.8 else 'Minor issues identified',
                    risk_level=random.choice(['low', 'medium']),
                    remediation_status='completed' if random.random() < 0.7 else 'pending'
                )
                session.add(audit)
                audit_count += 1
        
        # Incident Reports
        for i in range(random.randint(5, 20)):
            incident = IncidentReport(
                incident_id=f"INC{i:06d}",
                reported_by_id=random.choice(list(employees.keys())),
                department_id=random.choice(list(departments.values())).department_id,
                incident_type=random.choice(['Patient Safety', 'Security Breach', 'Data Loss', 'Other']),
                severity=random.choice(['low', 'medium', 'high']),
                description='Operational incident reported',
                status='resolved' if random.random() < 0.7 else 'investigating',
                hipaa_breach=random.random() < 0.05
            )
            session.add(incident)
            incident_count += 1
        
        session.commit()
        print(f"✓ Created 500 access logs, {audit_count} audits, {incident_count} incidents")
        
        # ====================================================================
        # FINAL REPORT
        # ====================================================================
        db_path = os.getenv("AEGIS_DB_PATH", "data/medical_company.db")
        print("\n" + "=" * 80)
        print("SAMPLE DATABASE SEEDING COMPLETE")
        print("=" * 80)
        print(f"\nSummary (all fictional — no real people or PHI):")
        print(f"  ✓ Locations: {len(locations)}")
        print(f"  ✓ Departments: {len(departments)}")
        print(f"  ✓ Teams: {total_teams}")
        print(f"  ✓ Employees: {len(employees)}")
        print(f"  ✓ Patients: {len(patients)}")
        print(f"  ✓ Appointments: {appt_count}")
        print(f"  ✓ Medical Records: {record_count}")
        print(f"  ✓ Prescriptions: {rx_count}")
        print(f"\nDatabase location: {db_path}")
        print("This is bundled DEMO data. In a real deployment, connect your own")
        print("sources and set AEGIS_DEMO_MODE=false to hide the sample-data notice.")
        print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during seeding: {str(e)}")
        session.rollback()
        return False
    finally:
        session.close()


if __name__ == '__main__':
    success = seed_database()
    sys.exit(0 if success else 1)
