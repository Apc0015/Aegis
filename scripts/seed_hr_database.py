"""
Seed script for 50-employee organization with 10 departments.
Run: python data/seed_50_employees.py
"""
import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = "data/hr_database.db"

# Department structure with realistic ratios
DEPARTMENTS = {
    "Engineering": {"headcount": 18, "levels": ["Junior", "Senior", "Staff", "Principal", "VP"]},
    "Product": {"headcount": 6, "levels": ["Associate", "Product Manager", "Senior PM", "Director"]},
    "Sales": {"headcount": 8, "levels": ["SDR", "AE", "Senior AE", "Sales Manager"]},
    "Marketing": {"headcount": 5, "levels": ["Specialist", "Manager", "Senior Manager", "Director"]},
    "HR": {"headcount": 3, "levels": ["Specialist", "Manager", "Director", "VP People"]},
    "Finance": {"headcount": 4, "levels": ["Analyst", "Senior Analyst", "Manager", "Controller"]},
    "Operations": {"headcount": 3, "levels": ["Coordinator", "Manager", "Director"]},
    "Customer_Success": {"headcount": 2, "levels": ["CSM", "Senior CSM", "Manager"]},
    "Legal": {"headcount": 2, "levels": ["Paralegal", "Counsel", "General Counsel"]},
    "IT": {"headcount": 4, "levels": ["Technician", "Specialist", "Manager", "Director"]},
}

FIRST_NAMES = [
    "James", "Maria", "Robert", "Jennifer", "Michael", "Linda", "William", "Patricia",
    "David", "Elizabeth", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah",
    "Charles", "Karen", "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Betty",
    "Mark", "Margaret", "Donald", "Sandra", "Steven", "Ashley", "Paul", "Kimberly",
    "Andrew", "Emily", "Joshua", "Donna", "Kenneth", "Michelle", "Kevin", "Dorothy",
    "Brian", "Carol", "George", "Amanda", "Edward", "Melissa", "Ronald", "Deborah",
    "Timothy", "Stephanie"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson",
    "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson",
    "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson", "Walker",
    "Young", "Allen", "King", "Wright", "Torres", "Nguyen", "Hill", "Flores",
    "Green", "Adams", "Nelson", "Baker", "Hall", "Rivera", "Campbell", "Mitchell"
]

JOB_TITLES = {
    "Engineering": ["Software Engineer", "Senior Software Engineer", "Staff Engineer", "Principal Engineer", "VP Engineering"],
    "Product": ["Associate PM", "Product Manager", "Senior Product Manager", "VP Product"],
    "Sales": ["Sales Development Rep", "Account Executive", "Senior Account Executive", "Sales Director"],
    "Marketing": ["Marketing Specialist", "Marketing Manager", "Senior Marketing Manager", "CMO"],
    "HR": ["HR Specialist", "HR Manager", "HR Director", "Chief People Officer"],
    "Finance": ["Financial Analyst", "Senior Financial Analyst", "Finance Manager", "Controller"],
    "Operations": ["Operations Coordinator", "Operations Manager", "VP Operations"],
    "Customer_Success": ["Customer Success Manager", "Senior CSM", "CS Director"],
    "Legal": ["Paralegal", "Legal Counsel", "General Counsel"],
    "IT": ["IT Technician", "IT Specialist", "IT Manager", "CTO"],
}

SALARY_RANGES = {
    "Engineering": (75000, 220000),
    "Product": (70000, 180000),
    "Sales": (60000, 200000),  # Plus commission
    "Marketing": (65000, 160000),
    "HR": (55000, 170000),
    "Finance": (65000, 175000),
    "Operations": (55000, 150000),
    "Customer_Success": (60000, 140000),
    "Legal": (70000, 250000),
    "IT": (60000, 180000),
}

def random_date(start, end):
    """Generate random date between start and end."""
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))

def generate_employee_id(dept_code, index):
    return f"EMP{dept_code}{index:03d}"

def seed_database():
    Path("data").mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing data (if tables exist)
    try:
        cursor.execute("DELETE FROM employees")
        cursor.execute("DELETE FROM leave_requests")
        cursor.execute("DELETE FROM benefits")
        cursor.execute("DELETE FROM employee_benefits")
        cursor.execute("DELETE FROM headcount_summary")
        cursor.execute("DELETE FROM policies")
        cursor.execute("DELETE FROM performance_reviews")
        cursor.execute("DELETE FROM training_records")
        cursor.execute("DELETE FROM organizational_chart")
    except sqlite3.OperationalError:
        pass  # Tables don't exist yet

    # Create tables
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

    CREATE TABLE IF NOT EXISTS performance_reviews (
        review_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        reviewer_id TEXT NOT NULL,
        review_period TEXT NOT NULL,
        rating INTEGER,
        goals TEXT,
        notes TEXT,
        submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    );

    CREATE TABLE IF NOT EXISTS training_records (
        record_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        training_name TEXT NOT NULL,
        completion_date DATE,
        status TEXT,
        score REAL,
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    );

    CREATE TABLE IF NOT EXISTS organizational_chart (
        node_id TEXT PRIMARY KEY,
        employee_id TEXT NOT NULL,
        parent_employee_id TEXT,
        level INTEGER,
        reporting_chain TEXT,
        FOREIGN KEY (employee_id) REFERENCES employees(employee_id)
    );
    """)

    # Generate 50 employees
    employees = []
    dept_codes = {
        "Engineering": "ENG", "Product": "PROD", "Sales": "SLS",
        "Marketing": "MKT", "HR": "HR", "Finance": "FIN",
        "Operations": "OPS", "Customer_Success": "CS", "Legal": "LEG", "IT": "IT"
    }

    emp_index = 1
    managers = {}  # Track managers per department

    for dept, info in DEPARTMENTS.items():
        dept_code = dept_codes[dept]
        headcount = info["headcount"]
        levels = info["levels"]

        for i in range(headcount):
            emp_id = generate_employee_id(dept_code, emp_index)
            first = random.choice(FIRST_NAMES)
            last = random.choice(LAST_NAMES)
            full_name = f"{first} {last}"

            # Determine level and job title
            if i == 0 and headcount > 1:
                level_idx = len(levels) - 1  # Department head
            elif i < headcount // 4:
                level_idx = len(levels) - 2  # Senior
            else:
                level_idx = random.randint(0, len(levels) - 2)

            job_title = JOB_TITLES[dept][level_idx]

            # Employment type
            if level_idx >= len(levels) - 2:  # Senior roles are FT
                emp_type = "full_time"
            else:
                emp_type = random.choices(
                    ["full_time", "part_time", "contractor"],
                    weights=[70, 15, 15]
                )[0]

            # Start date (between 2019 and 2025)
            start_date = random_date(datetime(2019, 1, 1), datetime(2025, 1, 1)).strftime("%Y-%m-%d")

            # Salary based on level and department
            min_sal, max_sal = SALARY_RANGES[dept]
            level_multiplier = 1 + (level_idx * 0.3)
            salary = int(random.uniform(min_sal * level_multiplier, max_sal * level_multiplier))
            salary_grade = f"L{level_idx + 1}"

            # Location
            location = random.choices(
                ["New York", "San Francisco", "Chicago", "Remote", "Austin", "Seattle"],
                weights=[30, 25, 15, 20, 5, 5]
            )[0]

            # SSN and email
            ssn = f"{random.randint(100, 999):03d}-{random.randint(10, 99):02d}-{random.randint(1000, 9999):04d}"
            personal_email = f"{first.lower()}.{last.lower()}@email.com"

            # Manager assignment
            if level_idx == len(levels) - 1:
                manager_id = None  # C-level reports to no one
            elif level_idx >= len(levels) - 2:
                # Senior reports to department head
                manager_id = managers.get(dept)
            else:
                # Others report to manager or department head
                manager_id = managers.get(dept) if random.random() > 0.5 else None

            if level_idx == len(levels) - 1:
                managers[dept] = emp_id

            employees.append((
                emp_id, full_name, dept.replace("_", " "), job_title, emp_type,
                start_date, manager_id, salary, salary_grade, location, ssn, personal_email, "active"
            ))

            emp_index += 1

    # Insert employees
    cursor.executemany("""
    INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, employees)

    # Generate leave requests (2-3 per employee)
    leave_requests = []
    leave_types = ["annual", "sick", "parental", "personal"]
    leave_statuses = ["approved", "approved", "approved", "pending", "rejected"]

    lr_index = 1
    for emp in employees:
        emp_id = emp[0]
        num_leaves = random.randint(1, 3)
        for _ in range(num_leaves):
            lr_id = f"LR{lr_index:04d}"
            leave_type = random.choice(leave_types)
            start = random_date(datetime(2025, 1, 1), datetime(2026, 6, 1))
            days = random.randint(1, 10) if leave_type != "parental" else random.randint(30, 90)
            end = start + timedelta(days=days)
            status = random.choice(leave_statuses)
            approved_by = random.choice([m for m in managers.values()]) if status == "approved" else None

            leave_requests.append((
                lr_id, emp_id, leave_type, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"),
                days, status, approved_by, "Auto-generated"
            ))
            lr_index += 1

    cursor.executemany("""
    INSERT INTO leave_requests (request_id, employee_id, leave_type, start_date, end_date,
    days_requested, status, approved_by, notes) VALUES (?,?,?,?,?,?,?,?,?)
    """, leave_requests)

    # Insert benefits
    benefits_data = [
        ("BEN001", "Health Insurance PPO", "Comprehensive medical, dental, vision coverage. Low deductible.", "all_employees", "2026-11-01", "2026-11-30", "BlueCross", "benefits@company.com"),
        ("BEN002", "Health Insurance HMO", "HMO plan with lower premiums. Primary care coordination.", "all_employees", "2026-11-01", "2026-11-30", "BlueCross", "benefits@company.com"),
        ("BEN003", "401k Plan", "Company matches 100% up to 4% of salary. Immediate vesting.", "full_time_only", "2026-01-01", "2026-01-31", "Fidelity", "401k@company.com"),
        ("BEN004", "Parental Leave", "16 weeks paid for primary caregivers. 6 weeks for secondary.", "all_employees", None, None, "Internal HR", "hr@company.com"),
        ("BEN005", "Learning Budget", "$2,500 annual professional development budget.", "full_time_only", None, None, "Internal HR", "hr@company.com"),
        ("BEN006", "Wellness Stipend", "$500 annual wellness stipend for gym, mental health, etc.", "all_employees", None, None, "Internal HR", "hr@company.com"),
        ("BEN007", "Commuter Benefits", "Pre-tax commuter benefits up to $300/month.", "all_employees", None, None, "Navia", "commuter@company.com"),
    ]
    cursor.executemany("""
    INSERT INTO benefits VALUES (?,?,?,?,?,?,?,?)
    """, benefits_data)

    # Employee benefits enrollment
    emp_benefits = []
    for emp in employees:
        emp_id = emp[0]
        emp_type = emp[4]
        for ben in benefits_data:
            if ben[1] == "401k Plan" and emp_type != "full_time":
                continue
            if random.random() > 0.3:  # 70% enrollment rate
                enroll_date = random_date(datetime(2019, 1, 1), datetime(2025, 1, 1))
                emp_benefits.append((emp_id, ben[0], enroll_date.strftime("%Y-%m-%d"), "active"))
    cursor.executemany("""
    INSERT INTO employee_benefits VALUES (?,?,?,?)
    """, emp_benefits)

    # Headcount summary
    today = datetime.now().strftime("%Y-%m-%d")
    for dept, info in DEPARTMENTS.items():
        ft = int(info["headcount"] * 0.75)
        pt = int(info["headcount"] * 0.15)
        contractors = info["headcount"] - ft - pt
        cursor.execute("""
        INSERT INTO headcount_summary VALUES (?,?,?,?,?,?,?)
        """, (today, dept.replace("_", " "), info["headcount"], ft, pt, contractors, 0))

    # Policies
    policies_data = [
        ("POL001", "Parental Leave Policy", "leave", "v3.0", "2025-01-01", "2025-01-01", "hr_documents/parental_leave.pdf", "16 weeks paid leave for primary caregivers. 6 weeks for secondary. Requires 12 months employment."),
        ("POL002", "Annual Leave Policy", "leave", "v4.1", "2024-06-01", "2024-06-01", "hr_documents/annual_leave.pdf", "20 days PTO starting. 25 days after 5 years. Unlimited for senior roles."),
        ("POL003", "Remote Work Policy", "conduct", "v2.0", "2024-01-15", "2024-01-15", "hr_documents/remote_work.pdf", "Hybrid model: 3 days office, 2 days remote. Full remote requires manager approval."),
        ("POL004", "Benefits Enrollment Guide", "benefits", "v5.0", "2026-01-01", "2026-01-01", "hr_documents/benefits_guide.pdf", "Open enrollment Nov 1-30. Life events allow changes within 30 days."),
        ("POL005", "Code of Conduct", "conduct", "v2.5", "2024-03-01", "2024-03-01", "hr_documents/code_of_conduct.pdf", "Professional behavior expected. Zero tolerance for harassment. Report violations to HR."),
        ("POL006", "Security Policy", "security", "v1.8", "2024-08-01", "2024-08-01", "hr_documents/security.pdf", "2FA required. Password manager mandatory. Phishing training required annually."),
        ("POL007", "Expense Policy", "finance", "v3.2", "2024-09-01", "2024-09-01", "hr_documents/expense.pdf", "Submit expenses within 30 days. $75 limit for meals. Pre-approval required for travel >$1000."),
        ("POL008", "Performance Review Process", "performance", "v2.0", "2024-11-01", "2024-11-01", "hr_documents/performance.pdf", "Quarterly check-ins. Annual 360 reviews. Ratings: Exceeds, Meets, Needs Improvement."),
    ]
    cursor.executemany("""
    INSERT INTO policies VALUES (?,?,?,?,?,?,?,?)
    """, policies_data)

    # Performance reviews
    reviews = []
    review_periods = ["2024-Q1", "2024-Q2", "2024-Q3", "2024-Q4"]
    for emp in employees:
        emp_id = emp[0]
        for period in review_periods:
            if random.random() > 0.2:  # 80% have reviews
                review_id = f"REV{emp_id}_{period}"
                reviewer_id = random.choice([m for m in managers.values() if m])
                rating = random.choices([5, 4, 3, 2], weights=[20, 50, 25, 5])[0]
                goals = "Complete assigned projects. Improve technical skills."
                notes = random.choice([
                    "Strong performance this quarter.",
                    "Met expectations. Room for growth.",
                    "Exceeded goals. Ready for more responsibility.",
                    "Solid contributor to the team.",
                ])
                reviews.append((review_id, emp_id, reviewer_id, period, rating, goals, notes))

    cursor.executemany("""
    INSERT INTO performance_reviews (review_id, employee_id, reviewer_id, review_period, rating, goals, notes)
    VALUES (?,?,?,?,?,?,?)
    """, reviews)

    # Training records
    trainings = [
        "Security Awareness 2024", "Unconscious Bias", "Manager Training", "AWS Certification",
        "Project Management", "Communication Skills", "Leadership Development"
    ]
    training_records = []
    for emp in employees:
        emp_id = emp[0]
        num_trainings = random.randint(1, 4)
        for t in random.sample(trainings, num_trainings):
            record_id = f"TRAIN{emp_id}_{t[:3].upper()}"
            completion = random_date(datetime(2023, 1, 1), datetime(2025, 6, 1))
            status = random.choice(["completed", "completed", "completed", "in_progress"])
            score = random.uniform(85, 100) if status == "completed" else None
            training_records.append((record_id, emp_id, t, completion.strftime("%Y-%m-%d"), status, score))

    cursor.executemany("""
    INSERT INTO training_records (record_id, employee_id, training_name, completion_date, status, score)
    VALUES (?,?,?,?,?,?)
    """, training_records)

    conn.commit()
    conn.close()
    print(f"✅ Seeded database with 50 employees across {len(DEPARTMENTS)} departments")
    print(f"✅ Generated {len(leave_requests)} leave requests")
    print(f"✅ Generated {len(reviews)} performance reviews")
    print(f"✅ Generated {len(training_records)} training records")

if __name__ == "__main__":
    seed_database()
