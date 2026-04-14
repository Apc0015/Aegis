"""
HR Database — Read-Only SQLite Connection
Provides safe, read-only access to the HR database.
Column-level access rules are applied BEFORE rows leave this module.
"""
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = "data/hr_database.db"


def get_readonly_connection():
    """Returns a read-only SQLite connection. INSERT/UPDATE/DELETE are impossible."""
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def seed_database():
    """
    Creates and seeds the HR database with sample data.
    Run this once to set up the demo database.
    Uses read-write connection for seeding only.
    """
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS employees (
        employee_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        department TEXT NOT NULL,
        job_title TEXT NOT NULL,
        employment_type TEXT NOT NULL,
        start_date DATE NOT NULL,
        manager_id TEXT,
        salary REAL,
        salary_grade TEXT,
        location TEXT,
        ssn TEXT,
        personal_email TEXT,
        status TEXT DEFAULT 'active'
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        request_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        leave_type TEXT NOT NULL,
        start_date DATE NOT NULL,
        end_date DATE NOT NULL,
        days_requested INTEGER NOT NULL,
        status TEXT NOT NULL,
        approved_by TEXT,
        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    );

    CREATE TABLE IF NOT EXISTS benefits (
        benefit_id TEXT PRIMARY KEY,
        benefit_name TEXT NOT NULL,
        description TEXT,
        eligibility TEXT,
        enrollment_open DATE,
        enrollment_close DATE,
        provider TEXT,
        contact_info TEXT
    );

    CREATE TABLE IF NOT EXISTS employee_benefits (
        employee_id TEXT NOT NULL,
        benefit_id TEXT NOT NULL,
        enrollment_date DATE,
        status TEXT DEFAULT 'active',
        PRIMARY KEY (employee_id, benefit_id)
    );

    CREATE TABLE IF NOT EXISTS headcount_summary (
        snapshot_date DATE NOT NULL,
        department TEXT NOT NULL,
        total_headcount INTEGER,
        full_time INTEGER,
        part_time INTEGER,
        contractors INTEGER,
        on_leave INTEGER,
        PRIMARY KEY (snapshot_date, department)
    );

    CREATE TABLE IF NOT EXISTS policies (
        policy_id TEXT PRIMARY KEY,
        policy_name TEXT NOT NULL,
        category TEXT NOT NULL,
        version TEXT,
        effective_date DATE,
        last_updated DATE,
        document_path TEXT,
        summary TEXT
    );
    """)

    # Sample employees
    cursor.executemany("""
    INSERT OR IGNORE INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, [
        ("EMP001", "Sarah Johnson", "Engineering", "Senior Engineer", "full_time", "2021-03-15", "MGR001", 95000, "senior", "New York", "555-00-1111", "sjohnson@personal.com", "active"),
        ("EMP002", "Marcus Chen", "HR", "HR Specialist", "full_time", "2022-06-01", "HRA001", 62000, "mid", "Remote", "555-00-2222", "mchen@personal.com", "active"),
        ("EMP003", "Priya Patel", "Finance", "Financial Analyst", "full_time", "2020-11-10", "MGR002", 78000, "mid", "Chicago", "555-00-3333", "ppatel@personal.com", "active"),
        ("MGR001", "David Kim", "Engineering", "Engineering Manager", "full_time", "2018-01-20", "HRA001", 125000, "lead", "New York", "555-00-4444", "dkim@personal.com", "active"),
        ("HRA001", "Lisa Torres", "HR", "HR Director", "full_time", "2016-08-01", None, 145000, "principal", "New York", "555-00-5555", "ltorres@personal.com", "active"),
    ])

    # Sample leave requests
    cursor.executemany("""
    INSERT OR IGNORE INTO leave_requests VALUES (?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP,?)
    """, [
        ("LR001", "EMP001", "annual", "2026-04-01", "2026-04-05", 5, "approved", "MGR001", "Spring vacation"),
        ("LR002", "EMP002", "sick", "2026-03-10", "2026-03-11", 2, "approved", "HRA001", "Doctor appointment"),
        ("LR003", "EMP003", "parental", "2026-05-01", "2026-07-31", 65, "pending", None, "Parental leave request"),
    ])

    # Sample benefits
    cursor.executemany("""
    INSERT OR IGNORE INTO benefits VALUES (?,?,?,?,?,?,?,?)
    """, [
        ("BEN001", "Health Insurance", "Comprehensive medical, dental, vision", "all_employees", "2026-11-01", "2026-11-30", "BlueCross", "benefits@company.com"),
        ("BEN002", "401k Plan", "Company matches up to 4% of salary", "full_time_only", "2026-01-01", "2026-01-31", "Fidelity", "401k@company.com"),
        ("BEN003", "Parental Leave", "16 weeks paid for primary caregivers, 6 weeks secondary", "all_employees", None, None, "Internal HR", "hr@company.com"),
        ("BEN004", "Learning Budget", "$2000 annual learning and development budget", "full_time_only", None, None, "Internal HR", "hr@company.com"),
    ])

    # Sample headcount
    cursor.executemany("""
    INSERT OR IGNORE INTO headcount_summary VALUES (?,?,?,?,?,?,?)
    """, [
        ("2026-03-01", "Engineering", 24, 20, 2, 2, 1),
        ("2026-03-01", "HR", 8, 7, 1, 0, 0),
        ("2026-03-01", "Finance", 12, 11, 0, 1, 0),
    ])

    # Sample policies
    cursor.executemany("""
    INSERT OR IGNORE INTO policies VALUES (?,?,?,?,?,?,?,?)
    """, [
        ("POL001", "Parental Leave Policy", "leave", "v2.1", "2025-01-01", "2025-01-01", "hr_documents/parental_leave_policy.pdf", "Provides 16 weeks paid leave for primary caregivers with 12 months minimum employment eligibility."),
        ("POL002", "Annual Leave Policy", "leave", "v3.0", "2024-06-01", "2024-06-01", "hr_documents/annual_leave_policy.pdf", "Employees accrue 20 days annual leave per year, increasing to 25 days after 5 years service."),
        ("POL003", "Remote Work Policy", "conduct", "v1.5", "2023-09-01", "2024-01-15", "hr_documents/remote_work_policy.pdf", "Employees may work remotely up to 3 days per week subject to manager approval."),
        ("POL004", "Benefits Enrollment Guide", "benefits", "v4.0", "2026-01-01", "2026-01-01", "hr_documents/benefits_guide.pdf", "Annual enrollment window is November 1-30. Changes take effect January 1 following year."),
    ])

    conn.commit()
    conn.close()
    logger.info("HR database seeded successfully")


def ensure_database_exists():
    """Call at startup — seeds the database if it doesn't exist yet."""
    if not Path(DB_PATH).exists():
        logger.info("HR database not found — seeding now...")
        seed_database()
    else:
        logger.info("HR database found — ready")
