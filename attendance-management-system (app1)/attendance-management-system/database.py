"""
database.py
Handles SQLite database connection, schema creation, and seeding
for the Attendance Management System.

Schema overview
---------------
users        -> admin login only
faculty      -> faculty master + faculty login
students     -> student master + student login
departments  -> department master
subjects     -> subject master (tied to a department + year)
timetable    -> which subject/faculty teaches a dept/year/section on a
                given day + hour/period
attendance   -> per-student, per-date, per-hour Present/Absent record
"""

import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_NAME = "attendance.db"
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, DB_NAME)

SCHEMA_VERSION = 2

DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
YEARS = [1, 2, 3, 4]
PERIODS = list(range(1, 9))  # Hour / Period 1-8
PASS_PERCENT = 75.0


# How long (seconds) a connection will wait for a lock held by another
# connection before giving up. Also mirrored via PRAGMA busy_timeout below
# (in milliseconds) so both the Python-level driver and SQLite's own
# internal busy-handler agree, which is what actually prevents
# "database is locked" errors under concurrent access.
DB_TIMEOUT_SECONDS = 30


def get_db_connection():
    """Return a sqlite3 connection with row access by column name.

    Configured to avoid 'database is locked' errors:
    - timeout=30s tells the sqlite3 driver to keep retrying instead of
      raising immediately if the database file is briefly locked by
      another connection.
    - PRAGMA busy_timeout mirrors that at the SQLite engine level.
    - WAL (Write-Ahead Logging) journal mode lets reads and writes happen
      concurrently instead of blocking each other, which is the main
      source of locking errors with the default rollback-journal mode.
    """
    conn = sqlite3.connect(DB_PATH, timeout=DB_TIMEOUT_SECONDS)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute(f"PRAGMA busy_timeout = {DB_TIMEOUT_SECONDS * 1000}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db():
    """Create tables if they do not exist, migrate old schema if needed, and seed defaults."""
    conn = get_db_connection()
    try:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS schema_info (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                version INTEGER NOT NULL
            )
        """)
        cur.execute("SELECT version FROM schema_info WHERE id = 1")
        row = cur.fetchone()
        current_version = row["version"] if row else 0

        if current_version < SCHEMA_VERSION:
            # Older/incompatible schema (e.g. students.class_name based) - rebuild the
            # data tables that changed shape. Master data tables are new, so this is safe.
            for old_table in ("attendance", "timetable", "students"):
                cur.execute(f"DROP TABLE IF EXISTS {old_table}")

        # ---------- Admin users ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # ---------- Departments ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                code TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # ---------- Faculty ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                department_id INTEGER,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
            )
        """)

        # ---------- Subjects ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                code TEXT,
                department_id INTEGER,
                year INTEGER,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
            )
        """)

        # ---------- Students ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                roll_no TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                department_id INTEGER,
                year INTEGER,
                section TEXT,
                email TEXT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE SET NULL
            )
        """)

        # ---------- Timetable ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS timetable (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                department_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                section TEXT NOT NULL,
                day_of_week TEXT NOT NULL,
                hour INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                faculty_id INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (department_id) REFERENCES departments (id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE CASCADE,
                FOREIGN KEY (faculty_id) REFERENCES faculty (id) ON DELETE CASCADE,
                UNIQUE (department_id, year, section, day_of_week, hour)
            )
        """)

        # ---------- Attendance ----------
        cur.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                hour INTEGER NOT NULL,
                subject_id INTEGER,
                faculty_id INTEGER,
                status TEXT NOT NULL CHECK(status IN ('Present', 'Absent')),
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (student_id) REFERENCES students (id) ON DELETE CASCADE,
                FOREIGN KEY (subject_id) REFERENCES subjects (id) ON DELETE SET NULL,
                FOREIGN KEY (faculty_id) REFERENCES faculty (id) ON DELETE SET NULL,
                UNIQUE (student_id, date, hour)
            )
        """)

        # Seed default admin account: username=admin password=admin123
        cur.execute("SELECT COUNT(*) AS c FROM users")
        if cur.fetchone()["c"] == 0:
            cur.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                ("admin", generate_password_hash("admin123")),
            )

        cur.execute("INSERT OR REPLACE INTO schema_info (id, version) VALUES (1, ?)", (SCHEMA_VERSION,))

        conn.commit()
    finally:
        conn.close()


# =====================================================================
# Departments
# =====================================================================

def get_all_departments():
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT * FROM departments ORDER BY name ASC").fetchall()
    finally:
        conn.close()
    return rows


def get_department(dept_id):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM departments WHERE id = ?", (dept_id,)).fetchone()
    finally:
        conn.close()
    return row


def add_department(name, code):
    conn = get_db_connection()
    try:
        conn.execute("INSERT INTO departments (name, code) VALUES (?, ?)", (name, code))
        conn.commit()
    finally:
        conn.close()


def update_department(dept_id, name, code):
    conn = get_db_connection()
    try:
        conn.execute("UPDATE departments SET name = ?, code = ? WHERE id = ?", (name, code, dept_id))
        conn.commit()
    finally:
        conn.close()


def delete_department(dept_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM departments WHERE id = ?", (dept_id,))
        conn.commit()
    finally:
        conn.close()


# =====================================================================
# Faculty
# =====================================================================

def get_all_faculty():
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT f.*, d.name AS department_name
            FROM faculty f
            LEFT JOIN departments d ON d.id = f.department_id
            ORDER BY f.name ASC
        """).fetchall()
    finally:
        conn.close()
    return rows


def get_faculty(faculty_id):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM faculty WHERE id = ?", (faculty_id,)).fetchone()
    finally:
        conn.close()
    return row


def get_faculty_by_username(username):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM faculty WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()
    return row


def add_faculty(name, email, phone, department_id, username, password):
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO faculty (name, email, phone, department_id, username, password_hash)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (name, email, phone, department_id, username, generate_password_hash(password)),
        )
        conn.commit()
    finally:
        conn.close()


def update_faculty(faculty_id, name, email, phone, department_id, username, password=None):
    conn = get_db_connection()
    try:
        if password:
            conn.execute(
                """UPDATE faculty SET name=?, email=?, phone=?, department_id=?, username=?, password_hash=?
                   WHERE id=?""",
                (name, email, phone, department_id, username, generate_password_hash(password), faculty_id),
            )
        else:
            conn.execute(
                """UPDATE faculty SET name=?, email=?, phone=?, department_id=?, username=?
                   WHERE id=?""",
                (name, email, phone, department_id, username, faculty_id),
            )
        conn.commit()
    finally:
        conn.close()


def delete_faculty(faculty_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM faculty WHERE id = ?", (faculty_id,))
        conn.commit()
    finally:
        conn.close()


# =====================================================================
# Subjects
# =====================================================================

def get_all_subjects(department_id=None, year=None):
    conn = get_db_connection()
    try:
        query = """
            SELECT s.*, d.name AS department_name
            FROM subjects s
            LEFT JOIN departments d ON d.id = s.department_id
            WHERE 1=1
        """
        params = []
        if department_id:
            query += " AND s.department_id = ?"
            params.append(department_id)
        if year:
            query += " AND s.year = ?"
            params.append(year)
        query += " ORDER BY s.name ASC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return rows


def get_subject(subject_id):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM subjects WHERE id = ?", (subject_id,)).fetchone()
    finally:
        conn.close()
    return row


def add_subject(name, code, department_id, year):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO subjects (name, code, department_id, year) VALUES (?, ?, ?, ?)",
            (name, code, department_id, year),
        )
        conn.commit()
    finally:
        conn.close()


def update_subject(subject_id, name, code, department_id, year):
    conn = get_db_connection()
    try:
        conn.execute(
            "UPDATE subjects SET name=?, code=?, department_id=?, year=? WHERE id=?",
            (name, code, department_id, year, subject_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_subject(subject_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM subjects WHERE id = ?", (subject_id,))
        conn.commit()
    finally:
        conn.close()


# =====================================================================
# Students
# =====================================================================

def get_all_students(department_id=None, year=None, section=None, search=None):
    conn = get_db_connection()
    try:
        query = """
            SELECT st.*, d.name AS department_name
            FROM students st
            LEFT JOIN departments d ON d.id = st.department_id
            WHERE 1=1
        """
        params = []
        if department_id:
            query += " AND st.department_id = ?"
            params.append(department_id)
        if year:
            query += " AND st.year = ?"
            params.append(year)
        if section:
            query += " AND st.section = ?"
            params.append(section)
        if search:
            query += " AND (st.name LIKE ? OR st.roll_no LIKE ? OR st.email LIKE ?)"
            like = f"%{search}%"
            params += [like, like, like]
        query += " ORDER BY st.name ASC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return rows


def get_student(student_id):
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT st.*, d.name AS department_name
            FROM students st
            LEFT JOIN departments d ON d.id = st.department_id
            WHERE st.id = ?
        """, (student_id,)).fetchone()
    finally:
        conn.close()
    return row


def get_student_by_username(username):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM students WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()
    return row


def get_students_by_class(department_id, year, section):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM students WHERE department_id = ? AND year = ? AND section = ?
               ORDER BY name ASC""",
            (department_id, year, section),
        ).fetchall()
    finally:
        conn.close()
    return rows


def add_student(roll_no, name, department_id, year, section, email, username, password):
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO students (roll_no, name, department_id, year, section, email, username, password_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (roll_no, name, department_id, year, section, email, username, generate_password_hash(password)),
        )
        conn.commit()
    finally:
        conn.close()


def update_student(student_id, roll_no, name, department_id, year, section, email, username, password=None):
    conn = get_db_connection()
    try:
        if password:
            conn.execute(
                """UPDATE students SET roll_no=?, name=?, department_id=?, year=?, section=?, email=?,
                   username=?, password_hash=? WHERE id=?""",
                (roll_no, name, department_id, year, section, email, username,
                 generate_password_hash(password), student_id),
            )
        else:
            conn.execute(
                """UPDATE students SET roll_no=?, name=?, department_id=?, year=?, section=?, email=?,
                   username=? WHERE id=?""",
                (roll_no, name, department_id, year, section, email, username, student_id),
            )
        conn.commit()
    finally:
        conn.close()


def delete_student(student_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM students WHERE id = ?", (student_id,))
        conn.commit()
    finally:
        conn.close()


def get_distinct_sections(department_id=None, year=None):
    conn = get_db_connection()
    try:
        query = "SELECT DISTINCT section FROM students WHERE section IS NOT NULL AND section != ''"
        params = []
        if department_id:
            query += " AND department_id = ?"
            params.append(department_id)
        if year:
            query += " AND year = ?"
            params.append(year)
        query += " ORDER BY section ASC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()
    return [r["section"] for r in rows]


# =====================================================================
# Timetable
# =====================================================================

def get_timetable(department_id=None, year=None, section=None):
    conn = get_db_connection()
    try:
        query = """
            SELECT t.*, d.name AS department_name, sub.name AS subject_name,
                   f.name AS faculty_name
            FROM timetable t
            LEFT JOIN departments d ON d.id = t.department_id
            LEFT JOIN subjects sub ON sub.id = t.subject_id
            LEFT JOIN faculty f ON f.id = t.faculty_id
            WHERE 1=1
        """
        params = []
        if department_id:
            query += " AND t.department_id = ?"
            params.append(department_id)
        if year:
            query += " AND t.year = ?"
            params.append(year)
        if section:
            query += " AND t.section = ?"
            params.append(section)
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    day_order = {d: i for i, d in enumerate(DAYS_OF_WEEK)}
    rows = sorted(rows, key=lambda r: (day_order.get(r["day_of_week"], 99), r["hour"]))
    return rows


def get_timetable_entry(entry_id):
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT * FROM timetable WHERE id = ?", (entry_id,)).fetchone()
    finally:
        conn.close()
    return row


def find_timetable_slot(department_id, year, section, day_of_week, hour):
    """Look up which subject/faculty teaches this exact dept/year/section/day/hour slot."""
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT t.*, sub.name AS subject_name, f.name AS faculty_name
            FROM timetable t
            LEFT JOIN subjects sub ON sub.id = t.subject_id
            LEFT JOIN faculty f ON f.id = t.faculty_id
            WHERE t.department_id = ? AND t.year = ? AND t.section = ?
                  AND t.day_of_week = ? AND t.hour = ?
            """,
            (department_id, year, section, day_of_week, hour),
        ).fetchone()
    finally:
        conn.close()
    return row


def add_timetable_entry(department_id, year, section, day_of_week, hour, subject_id, faculty_id):
    conn = get_db_connection()
    try:
        conn.execute(
            """INSERT INTO timetable (department_id, year, section, day_of_week, hour, subject_id, faculty_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (department_id, year, section, day_of_week, hour, subject_id, faculty_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_timetable_entry(entry_id, department_id, year, section, day_of_week, hour, subject_id, faculty_id):
    conn = get_db_connection()
    try:
        conn.execute(
            """UPDATE timetable SET department_id=?, year=?, section=?, day_of_week=?, hour=?,
               subject_id=?, faculty_id=? WHERE id=?""",
            (department_id, year, section, day_of_week, hour, subject_id, faculty_id, entry_id),
        )
        conn.commit()
    finally:
        conn.close()


def delete_timetable_entry(entry_id):
    conn = get_db_connection()
    try:
        conn.execute("DELETE FROM timetable WHERE id = ?", (entry_id,))
        conn.commit()
    finally:
        conn.close()


# =====================================================================
# Attendance
# =====================================================================

def mark_attendance(student_id, date, hour, subject_id, faculty_id, status):
    conn = get_db_connection()
    try:
        conn.execute(
            """
            INSERT INTO attendance (student_id, date, hour, subject_id, faculty_id, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(student_id, date, hour)
            DO UPDATE SET status = excluded.status, subject_id = excluded.subject_id,
                          faculty_id = excluded.faculty_id
            """,
            (student_id, date, hour, subject_id, faculty_id, status),
        )
        conn.commit()
    finally:
        conn.close()


def get_attendance_for_session(department_id, year, section, date, hour):
    """Students of a class + their attendance status for one specific date+hour."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT st.id AS student_id, st.roll_no, st.name, a.status
            FROM students st
            LEFT JOIN attendance a ON a.student_id = st.id AND a.date = ? AND a.hour = ?
            WHERE st.department_id = ? AND st.year = ? AND st.section = ?
            ORDER BY st.name ASC
            """,
            (date, hour, department_id, year, section),
        ).fetchall()
    finally:
        conn.close()
    return rows


def compute_leave_stats(present, total, pass_percent=PASS_PERCENT):
    """Return (percentage, remaining_leave, days_required_for_75) for a student.

    - remaining_leave: additional classes the student can miss going forward
      while the overall percentage stays >= pass_percent (meaningful once
      already eligible).
    - days_required: consecutive future classes the student must attend
      (assuming all are attended) so the overall percentage reaches
      pass_percent (meaningful while below it).
    Rounding always favors the student never being told fewer classes than
    are actually required (ceil), and never being told they can take more
    leave than is actually safe (floor).
    """
    if total <= 0:
        return 0.0, 0, 0
    pct = round((present / total) * 100, 1)
    threshold = pass_percent / 100.0
    if pct >= pass_percent:
        remaining_leave = int((present / threshold) - total)
        remaining_leave = max(remaining_leave, 0)
        days_required = 0
    else:
        remaining_leave = 0
        needed = (pass_percent * total - 100 * present) / (100 - pass_percent)
        days_required = max(int(-(-needed // 1)), 0)  # ceil, never undercount
    return pct, remaining_leave, days_required


def get_eligibility_status(total, percentage, pass_percent=PASS_PERCENT):
    """Return (status_text, status_class) for a student's attendance record.
    status_class is 'good' (>= pass_percent), 'bad' (< pass_percent), or
    'neutral' (no classes recorded yet, nothing to judge)."""
    if total <= 0:
        return "No Attendance Records", "neutral"
    if percentage >= pass_percent:
        return "Attendance Eligible", "good"
    return "Attendance Below 75%", "bad"


def _build_attendance_summary(present, absent, total):
    """Shared helper producing the full attendance-analysis fields
    (percentage, eligibility, remaining leave, classes needed) for any
    present/absent/total triple. Safe for total == 0."""
    pct, remaining_leave, days_required = compute_leave_stats(present, total)
    status_text, status_class = get_eligibility_status(total, pct)
    return {
        "present_count": present,
        "absent_count": absent,
        "total_count": total,
        "percentage": pct,
        "remaining_leave": remaining_leave,
        "days_required": days_required,
        "status_text": status_text,
        "status_class": status_class,
    }


def get_student_attendance_stats(student_id):
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                COUNT(*) AS total_count
            FROM attendance WHERE student_id = ?
            """,
            (student_id,),
        ).fetchone()
    finally:
        conn.close()
    present = row["present_count"] or 0
    absent = row["absent_count"] or 0
    total = row["total_count"] or 0
    summary = _build_attendance_summary(present, absent, total)
    # Keep original key names ("present"/"absent"/"total") for backward
    # compatibility with existing templates, plus the new analysis fields.
    return {
        "present": present,
        "absent": absent,
        "total": total,
        "percentage": summary["percentage"],
        "remaining_leave": summary["remaining_leave"],
        "days_required": summary["days_required"],
        "status_text": summary["status_text"],
        "status_class": summary["status_class"],
    }


def get_student_subject_wise_stats(student_id):
    """Per-subject attendance breakdown for a single student, with the same
    eligibility/remaining-leave/classes-needed analysis as the overall stats.
    Reads directly from the attendance table, so it updates automatically
    the moment new attendance is marked."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT sub.id AS subject_id, sub.name AS subject_name,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                   COUNT(a.id) AS total_count
            FROM attendance a
            LEFT JOIN subjects sub ON sub.id = a.subject_id
            WHERE a.student_id = ?
            GROUP BY sub.id
            ORDER BY sub.name ASC
            """,
            (student_id,),
        ).fetchall()
    finally:
        conn.close()

    summary = []
    for r in rows:
        present = r["present_count"] or 0
        absent = r["absent_count"] or 0
        total = r["total_count"] or 0
        entry = _build_attendance_summary(present, absent, total)
        entry["subject_id"] = r["subject_id"]
        entry["subject_name"] = r["subject_name"] or "-"
        summary.append(entry)
    return summary


def get_student_history(student_id):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT a.date, a.hour, a.status, sub.name AS subject_name, f.name AS faculty_name
            FROM attendance a
            LEFT JOIN subjects sub ON sub.id = a.subject_id
            LEFT JOIN faculty f ON f.id = a.faculty_id
            WHERE a.student_id = ?
            ORDER BY a.date DESC, a.hour DESC
            """,
            (student_id,),
        ).fetchall()
    finally:
        conn.close()
    return rows


# =====================================================================
# Reports
# =====================================================================

def _student_summary_rows(where_clause="", params=None):
    """Shared aggregation: per-student present/absent/total/percentage, with joins
    to department for filtering/display, optionally constrained by where_clause."""
    params = params or []
    conn = get_db_connection()
    try:
        rows = conn.execute(
            f"""
            SELECT st.id AS student_id, st.roll_no, st.name, st.year, st.section,
                   d.name AS department_name,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                   COUNT(a.id) AS total_count
            FROM students st
            LEFT JOIN departments d ON d.id = st.department_id
            LEFT JOIN attendance a ON a.student_id = st.id
            WHERE 1=1 {where_clause}
            GROUP BY st.id
            ORDER BY st.name ASC
            """,
            params,
        ).fetchall()
    finally:
        conn.close()

    summary = []
    for r in rows:
        present = r["present_count"] or 0
        absent = r["absent_count"] or 0
        total = r["total_count"] or 0
        stats = _build_attendance_summary(present, absent, total)
        summary.append({
            "student_id": r["student_id"],
            "roll_no": r["roll_no"],
            "name": r["name"],
            "year": r["year"],
            "section": r["section"],
            "department_name": r["department_name"],
            "present_count": present,
            "absent_count": absent,
            "total_count": total,
            "percentage": stats["percentage"],
            "remaining_leave": stats["remaining_leave"],
            "days_required": stats["days_required"],
            "status_text": stats["status_text"],
            "status_class": stats["status_class"],
        })
    return summary


def get_student_wise_report(student_id=None):
    if student_id:
        return _student_summary_rows("AND st.id = ?", [student_id])
    return _student_summary_rows()


def get_department_wise_report(department_id=None):
    if department_id:
        return _student_summary_rows("AND st.department_id = ?", [department_id])
    return _student_summary_rows()


def get_year_wise_report(year=None):
    if year:
        return _student_summary_rows("AND st.year = ?", [year])
    return _student_summary_rows()


def get_section_wise_report(section=None):
    if section:
        return _student_summary_rows("AND st.section = ?", [section])
    return _student_summary_rows()


def get_students_below_75():
    all_rows = _student_summary_rows()
    return [r for r in all_rows if r["total_count"] > 0 and r["percentage"] < PASS_PERCENT]


def get_daily_report(date):
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT st.roll_no, st.name, st.year, st.section, d.name AS department_name,
                   a.hour, sub.name AS subject_name, f.name AS faculty_name, a.status
            FROM attendance a
            JOIN students st ON st.id = a.student_id
            LEFT JOIN departments d ON d.id = st.department_id
            LEFT JOIN subjects sub ON sub.id = a.subject_id
            LEFT JOIN faculty f ON f.id = a.faculty_id
            WHERE a.date = ?
            ORDER BY a.hour ASC, st.name ASC
            """,
            (date,),
        ).fetchall()
    finally:
        conn.close()
    return rows


def get_monthly_report(year_month):
    """year_month like '2026-07'."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT st.id AS student_id, st.roll_no, st.name, st.year, st.section,
                   d.name AS department_name,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                   COUNT(a.id) AS total_count
            FROM students st
            LEFT JOIN departments d ON d.id = st.department_id
            LEFT JOIN attendance a ON a.student_id = st.id AND substr(a.date, 1, 7) = ?
            GROUP BY st.id
            HAVING total_count > 0
            ORDER BY st.name ASC
            """,
            (year_month,),
        ).fetchall()
    finally:
        conn.close()

    summary = []
    for r in rows:
        present = r["present_count"] or 0
        absent = r["absent_count"] or 0
        total = r["total_count"] or 0
        stats = _build_attendance_summary(present, absent, total)
        summary.append({
            "roll_no": r["roll_no"], "name": r["name"], "year": r["year"],
            "section": r["section"], "department_name": r["department_name"],
            "present_count": present, "absent_count": absent,
            "total_count": total, "percentage": stats["percentage"],
            "remaining_leave": stats["remaining_leave"],
            "days_required": stats["days_required"],
            "status_text": stats["status_text"],
            "status_class": stats["status_class"],
        })
    return summary


def get_subject_wise_report(subject_id=None):
    conn = get_db_connection()
    try:
        query = """
            SELECT sub.id AS subject_id, sub.name AS subject_name,
                   SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present_count,
                   SUM(CASE WHEN a.status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
                   COUNT(a.id) AS total_count
            FROM subjects sub
            LEFT JOIN attendance a ON a.subject_id = sub.id
            WHERE 1=1
        """
        params = []
        if subject_id:
            query += " AND sub.id = ?"
            params.append(subject_id)
        query += " GROUP BY sub.id ORDER BY sub.name ASC"
        rows = conn.execute(query, params).fetchall()
    finally:
        conn.close()

    summary = []
    for r in rows:
        present = r["present_count"] or 0
        total = r["total_count"] or 0
        pct, _, _ = compute_leave_stats(present, total)
        summary.append({
            "subject_id": r["subject_id"], "subject_name": r["subject_name"],
            "present_count": present, "absent_count": r["absent_count"] or 0,
            "total_count": total, "percentage": pct,
        })
    return summary


def get_all_attendance_rows():
    """Used for CSV export - full attendance table joined with student info."""
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT st.roll_no, st.name, d.name AS department_name, st.year, st.section,
                   a.date, a.hour, sub.name AS subject_name, a.status
            FROM attendance a
            JOIN students st ON st.id = a.student_id
            LEFT JOIN departments d ON d.id = st.department_id
            LEFT JOIN subjects sub ON sub.id = a.subject_id
            ORDER BY a.date DESC, a.hour ASC, st.name ASC
            """
        ).fetchall()
    finally:
        conn.close()
    return rows


# =====================================================================
# Admin users
# =====================================================================

def get_user_by_username(username):
    conn = get_db_connection()
    try:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    finally:
        conn.close()
    return user
