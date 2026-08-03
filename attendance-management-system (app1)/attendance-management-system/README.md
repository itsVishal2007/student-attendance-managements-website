# Attendance Management System

A college Attendance Management System built with **Flask** and **SQLite**,
with role-based login for Admin, Faculty, and Students, full master-data
management, a timetable-driven attendance workflow, and a complete reports
suite.

## Features

- 🔐 **Role-based login** — Admin, Faculty, and Student, each with their own
  session and dashboard.
- 🏫 **Master modules** (Admin only) — Department, Faculty, Subject, and
  Student, each with Add / Edit / Delete. Students can also be searched and
  filtered by Department / Year / Section.
- 🗓️ **Timetable module** — Admin builds the timetable by choosing
  Department, Year, Section, Day, Hour/Period, Subject, and Faculty.
  Subject and Faculty are always picked from dropdowns backed by the
  Subject/Faculty tables — never typed freehand.
- ✅ **Attendance module** — Faculty (or Admin) select Department, Year,
  Section, Date, and Hour; the subject and faculty for that slot are
  **automatically loaded from the timetable**. Only students belonging to
  that Department/Year/Section are listed, and each is marked
  Present/Absent.
- 🎓 **Student dashboard** — Present days, Absent days, Attendance %,
  Remaining leave while staying ≥ 75%, and Days required to reach 75%.
- 📊 **Reports** (Admin) — Daily, Monthly, Student-wise, Subject-wise,
  Department-wise, Year-wise, Section-wise, and Students Below 75%.
- ⬇️ Export the full attendance log to CSV.
- 🗂 Per-student attendance history (subject, faculty, hour, status).

All master data (departments, faculty, subjects, students, timetable,
attendance) is created through the website and stored in SQLite — nothing
is hardcoded.

## Project Structure

```
attendance-management-system/
├── app.py                     # Flask application & routes
├── database.py                # SQLite schema, connection, and query helpers
├── requirements.txt           # Python dependencies
├── README.md
├── attendance.db              # Created automatically on first run
├── templates/                 # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html          # Admin / Faculty / Student views
│   ├── departments.html / department_form.html
│   ├── faculty.html / faculty_form.html
│   ├── subjects.html / subject_form.html
│   ├── students.html / student_form.html / student_history.html
│   ├── timetable.html / timetable_form.html
│   ├── attendance.html
│   ├── reports.html / _report_summary_table.html
└── static/
    ├── css/style.css
    └── js/script.js
```

## Requirements

- Python 3.9+
- pip

## Setup & Run

1. **Open the project folder in VS Code** (unzip it first, then `File > Open Folder`).

2. **(Recommended) Create a virtual environment:**

   ```bash
   python -m venv venv
   ```

   Activate it:
   - Windows: `venv\Scripts\activate`
   - macOS/Linux: `source venv/bin/activate`

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application:**

   ```bash
   python app.py
   ```

5. Open your browser at **http://127.0.0.1:5000**

The SQLite database (`attendance.db`) is created automatically the first
time you run `app.py`, seeded only with a default Admin account. Everything
else (departments, faculty, subjects, students, timetable) is added by the
Admin through the site.

## Default Login

| Role  | Username | Password  |
|-------|----------|-----------|
| Admin | admin    | admin123  |

Faculty and Student accounts are created by the Admin under
**Master > Faculty** and **Master > Students** — each account's username
and password are set at creation time.

> ⚠️ Change the default admin password and the Flask `secret_key` in
> `app.py` before deploying this anywhere beyond your own machine.

## Suggested Setup Order

1. Log in as Admin.
2. Create **Departments**.
3. Create **Faculty** (assign a Department + login credentials).
4. Create **Subjects** (assign a Department + Year).
5. Create **Students** (assign Department/Year/Section + login credentials).
6. Build the **Timetable** (Department, Year, Section, Day, Hour, Subject,
   Faculty).
7. Faculty logs in and uses **Mark Attendance** — the subject is loaded
   automatically from the timetable for the chosen date/hour.
8. Students log in to see their own attendance stats; Admin uses
   **Reports** for the full picture.

## Resetting the Data

To start fresh, stop the app and delete `attendance.db`, then run
`python app.py` again — it will be recreated with only the default admin
account.

## Notes

- This project uses Flask's built-in development server (`debug=True`),
  which is fine for learning/local use but is **not** intended for
  production. For production, use a WSGI server such as Gunicorn or
  Waitress behind a reverse proxy, and set `debug=False`.
- All data is stored locally in `attendance.db` (SQLite) — no external
  services or internet connection are required.
- The 75% "remaining leave" / "days required" figures assume the class
  size (number of hours held) stays roughly constant going forward; they
  are a planning aid, not an official academic record.
