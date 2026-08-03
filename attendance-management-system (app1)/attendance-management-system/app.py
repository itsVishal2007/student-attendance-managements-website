"""
app.py
Main Flask application for the Attendance Management System.

Run with:
    pip install -r requirements.txt
    python app.py

Default logins:
    Admin   -> username: admin     password: admin123
    Faculty -> created by Admin under Master > Faculty
    Student -> created by Admin under Master > Student
"""

import csv
import io
import os
from datetime import date, datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, Response
)
from werkzeug.security import check_password_hash

import database as db

app = Flask(__name__)
app.secret_key = "change-this-secret-key-in-production"

DAYS_OF_WEEK = db.DAYS_OF_WEEK
YEARS = db.YEARS
PERIODS = db.PERIODS


# ---------- Auth helpers ----------

def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))
        return view_func(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))
            if session.get("role") not in roles:
                flash("You do not have permission to view that page.", "error")
                return redirect(url_for("dashboard"))
            return view_func(*args, **kwargs)
        return wrapped
    return decorator


@app.context_processor
def inject_user():
    return {
        "current_user": session.get("username"),
        "current_role": session.get("role"),
    }


# ---------- Auth routes ----------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "admin")
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if role == "admin":
            user = db.get_user_by_username(username)
            if user and check_password_hash(user["password_hash"], password):
                session.clear()
                session["user_id"] = f"admin-{user['id']}"
                session["username"] = user["username"]
                session["role"] = "admin"
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))

        elif role == "faculty":
            fac = db.get_faculty_by_username(username)
            if fac and check_password_hash(fac["password_hash"], password):
                session.clear()
                session["user_id"] = f"faculty-{fac['id']}"
                session["username"] = fac["username"]
                session["role"] = "faculty"
                session["faculty_id"] = fac["id"]
                session["faculty_name"] = fac["name"]
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))

        elif role == "student":
            stu = db.get_student_by_username(username)
            if stu and check_password_hash(stu["password_hash"], password):
                session.clear()
                session["user_id"] = f"student-{stu['id']}"
                session["username"] = stu["username"]
                session["role"] = "student"
                session["student_id"] = stu["id"]
                session["student_name"] = stu["name"]
                flash("Logged in successfully.", "success")
                return redirect(url_for("dashboard"))

        flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# ---------- Dashboard ----------

@app.route("/")
@login_required
def dashboard():
    role = session.get("role")

    if role == "student":
        stats = db.get_student_attendance_stats(session["student_id"])
        subject_stats = db.get_student_subject_wise_stats(session["student_id"])
        student = db.get_student(session["student_id"])
        return render_template("dashboard.html", role=role, student=student,
                                stats=stats, subject_stats=subject_stats)

    if role == "faculty":
        today_name = date.today().strftime("%A")
        todays_classes = [
            t for t in db.get_timetable() if t["faculty_id"] == session["faculty_id"]
            and t["day_of_week"] == today_name
        ]
        todays_classes.sort(key=lambda t: t["hour"])
        return render_template("dashboard.html", role=role, todays_classes=todays_classes, today=date.today().isoformat())

    # admin
    students = db.get_all_students()
    departments = db.get_all_departments()
    faculty = db.get_all_faculty()
    subjects = db.get_all_subjects()
    today = date.today().isoformat()
    today_attendance = db.get_daily_report(today)

    present_today = sum(1 for r in today_attendance if r["status"] == "Present")
    absent_today = sum(1 for r in today_attendance if r["status"] == "Absent")
    below_75 = db.get_students_below_75()

    return render_template(
        "dashboard.html",
        role=role,
        total_students=len(students),
        total_departments=len(departments),
        total_faculty=len(faculty),
        total_subjects=len(subjects),
        today=today,
        present_today=present_today,
        absent_today=absent_today,
        below_75_count=len(below_75),
    )


# =====================================================================
# MASTER MODULE: Departments
# =====================================================================

@app.route("/departments")
@role_required("admin")
def departments():
    all_departments = db.get_all_departments()
    return render_template("departments.html", departments=all_departments)


@app.route("/departments/add", methods=["GET", "POST"])
@role_required("admin")
def add_department():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        if not name:
            flash("Department name is required.", "error")
            return render_template("department_form.html", department=None, action="Add")
        try:
            db.add_department(name, code)
            flash(f"Department '{name}' added successfully.", "success")
            return redirect(url_for("departments"))
        except Exception as e:
            flash(f"Error adding department: {e}", "error")
    return render_template("department_form.html", department=None, action="Add")


@app.route("/departments/edit/<int:dept_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_department(dept_id):
    department = db.get_department(dept_id)
    if not department:
        flash("Department not found.", "error")
        return redirect(url_for("departments"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        if not name:
            flash("Department name is required.", "error")
            return render_template("department_form.html", department=department, action="Edit")
        try:
            db.update_department(dept_id, name, code)
            flash(f"Department '{name}' updated successfully.", "success")
            return redirect(url_for("departments"))
        except Exception as e:
            flash(f"Error updating department: {e}", "error")

    return render_template("department_form.html", department=department, action="Edit")


@app.route("/departments/delete/<int:dept_id>", methods=["POST"])
@role_required("admin")
def delete_department(dept_id):
    department = db.get_department(dept_id)
    if department:
        try:
            db.delete_department(dept_id)
            flash(f"Department '{department['name']}' deleted.", "success")
        except Exception as e:
            flash(f"Cannot delete department: {e}", "error")
    return redirect(url_for("departments"))


# =====================================================================
# MASTER MODULE: Faculty
# =====================================================================

@app.route("/faculty")
@role_required("admin")
def faculty_list():
    all_faculty = db.get_all_faculty()
    return render_template("faculty.html", faculty=all_faculty)


@app.route("/faculty/add", methods=["GET", "POST"])
@role_required("admin")
def add_faculty():
    departments = db.get_all_departments()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id") or None
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not name or not username or not password:
            flash("Name, username, and password are required.", "error")
            return render_template("faculty_form.html", faculty=None, action="Add", departments=departments)
        try:
            db.add_faculty(name, email, phone, department_id, username, password)
            flash(f"Faculty '{name}' added successfully.", "success")
            return redirect(url_for("faculty_list"))
        except Exception as e:
            flash(f"Error adding faculty: {e}", "error")

    return render_template("faculty_form.html", faculty=None, action="Add", departments=departments)


@app.route("/faculty/edit/<int:faculty_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_faculty(faculty_id):
    fac = db.get_faculty(faculty_id)
    departments = db.get_all_departments()
    if not fac:
        flash("Faculty not found.", "error")
        return redirect(url_for("faculty_list"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        department_id = request.form.get("department_id") or None
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not name or not username:
            flash("Name and username are required.", "error")
            return render_template("faculty_form.html", faculty=fac, action="Edit", departments=departments)
        try:
            db.update_faculty(faculty_id, name, email, phone, department_id, username, password or None)
            flash(f"Faculty '{name}' updated successfully.", "success")
            return redirect(url_for("faculty_list"))
        except Exception as e:
            flash(f"Error updating faculty: {e}", "error")

    return render_template("faculty_form.html", faculty=fac, action="Edit", departments=departments)


@app.route("/faculty/delete/<int:faculty_id>", methods=["POST"])
@role_required("admin")
def delete_faculty(faculty_id):
    fac = db.get_faculty(faculty_id)
    if fac:
        try:
            db.delete_faculty(faculty_id)
            flash(f"Faculty '{fac['name']}' deleted.", "success")
        except Exception as e:
            flash(f"Cannot delete faculty: {e}", "error")
    return redirect(url_for("faculty_list"))


# =====================================================================
# MASTER MODULE: Subjects
# =====================================================================

@app.route("/subjects")
@role_required("admin")
def subjects():
    all_subjects = db.get_all_subjects()
    return render_template("subjects.html", subjects=all_subjects)


@app.route("/subjects/add", methods=["GET", "POST"])
@role_required("admin")
def add_subject():
    departments = db.get_all_departments()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        department_id = request.form.get("department_id") or None
        year = request.form.get("year") or None

        if not name:
            flash("Subject name is required.", "error")
            return render_template("subject_form.html", subject=None, action="Add",
                                    departments=departments, years=YEARS)
        try:
            db.add_subject(name, code, department_id, year)
            flash(f"Subject '{name}' added successfully.", "success")
            return redirect(url_for("subjects"))
        except Exception as e:
            flash(f"Error adding subject: {e}", "error")

    return render_template("subject_form.html", subject=None, action="Add",
                            departments=departments, years=YEARS)


@app.route("/subjects/edit/<int:subject_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_subject(subject_id):
    subject = db.get_subject(subject_id)
    departments = db.get_all_departments()
    if not subject:
        flash("Subject not found.", "error")
        return redirect(url_for("subjects"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        department_id = request.form.get("department_id") or None
        year = request.form.get("year") or None

        if not name:
            flash("Subject name is required.", "error")
            return render_template("subject_form.html", subject=subject, action="Edit",
                                    departments=departments, years=YEARS)
        try:
            db.update_subject(subject_id, name, code, department_id, year)
            flash(f"Subject '{name}' updated successfully.", "success")
            return redirect(url_for("subjects"))
        except Exception as e:
            flash(f"Error updating subject: {e}", "error")

    return render_template("subject_form.html", subject=subject, action="Edit",
                            departments=departments, years=YEARS)


@app.route("/subjects/delete/<int:subject_id>", methods=["POST"])
@role_required("admin")
def delete_subject(subject_id):
    subject = db.get_subject(subject_id)
    if subject:
        try:
            db.delete_subject(subject_id)
            flash(f"Subject '{subject['name']}' deleted.", "success")
        except Exception as e:
            flash(f"Cannot delete subject: {e}", "error")
    return redirect(url_for("subjects"))


# =====================================================================
# MASTER MODULE: Students (Add / Edit / Delete / Search)
# =====================================================================

@app.route("/students")
@role_required("admin")
def students():
    department_id = request.args.get("department_id") or None
    year = request.args.get("year") or None
    section = request.args.get("section") or None
    search = request.args.get("search") or None

    all_students = db.get_all_students(department_id, year, section, search)
    departments = db.get_all_departments()
    return render_template(
        "students.html",
        students=all_students,
        departments=departments,
        years=YEARS,
        filters={"department_id": department_id, "year": year, "section": section, "search": search or ""},
    )


@app.route("/students/add", methods=["GET", "POST"])
@role_required("admin")
def add_student():
    departments = db.get_all_departments()
    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        department_id = request.form.get("department_id") or None
        year = request.form.get("year") or None
        section = request.form.get("section", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not roll_no or not name or not username or not password:
            flash("Roll number, name, username, and password are required.", "error")
            return render_template("student_form.html", student=None, action="Add",
                                    departments=departments, years=YEARS)
        try:
            db.add_student(roll_no, name, department_id, year, section, email, username, password)
            flash(f"Student '{name}' added successfully.", "success")
            return redirect(url_for("students"))
        except Exception as e:
            flash(f"Error adding student: {e}", "error")

    return render_template("student_form.html", student=None, action="Add",
                            departments=departments, years=YEARS)


@app.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_student(student_id):
    student = db.get_student(student_id)
    departments = db.get_all_departments()
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("students"))

    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()
        department_id = request.form.get("department_id") or None
        year = request.form.get("year") or None
        section = request.form.get("section", "").strip()
        email = request.form.get("email", "").strip()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not roll_no or not name or not username:
            flash("Roll number, name, and username are required.", "error")
            return render_template("student_form.html", student=student, action="Edit",
                                    departments=departments, years=YEARS)
        try:
            db.update_student(student_id, roll_no, name, department_id, year, section,
                               email, username, password or None)
            flash(f"Student '{name}' updated successfully.", "success")
            return redirect(url_for("students"))
        except Exception as e:
            flash(f"Error updating student: {e}", "error")

    return render_template("student_form.html", student=student, action="Edit",
                            departments=departments, years=YEARS)


@app.route("/students/delete/<int:student_id>", methods=["POST"])
@role_required("admin")
def delete_student(student_id):
    student = db.get_student(student_id)
    if student:
        db.delete_student(student_id)
        flash(f"Student '{student['name']}' deleted.", "success")
    return redirect(url_for("students"))


@app.route("/students/<int:student_id>/history")
@login_required
def student_history(student_id):
    if session.get("role") == "student" and session.get("student_id") != student_id:
        flash("You can only view your own attendance history.", "error")
        return redirect(url_for("dashboard"))

    student = db.get_student(student_id)
    if not student:
        flash("Student not found.", "error")
        return redirect(url_for("dashboard"))
    history = db.get_student_history(student_id)
    stats = db.get_student_attendance_stats(student_id)
    subject_stats = db.get_student_subject_wise_stats(student_id)
    return render_template("student_history.html", student=student, history=history,
                            stats=stats, subject_stats=subject_stats)


# =====================================================================
# TIMETABLE MODULE (Admin creates)
# =====================================================================

@app.route("/timetable")
@role_required("admin", "faculty")
def timetable():
    departments = db.get_all_departments()
    department_id = request.args.get("department_id") or (departments[0]["id"] if departments else None)
    year = request.args.get("year") or None
    section = request.args.get("section") or None

    entries = db.get_timetable(department_id, year, section)
    sections = db.get_distinct_sections(department_id, year)

    # Build a Day x Hour lookup grid purely for display purposes.
    # This does not alter the underlying data or the "entries" list itself.
    grid = {day: {hour: None for hour in PERIODS} for day in DAYS_OF_WEEK}
    for e in entries:
        if e["day_of_week"] in grid and e["hour"] in grid[e["day_of_week"]]:
            grid[e["day_of_week"]][e["hour"]] = e

    return render_template(
        "timetable.html",
        entries=entries,
        grid=grid,
        days=DAYS_OF_WEEK,
        periods=PERIODS,
        departments=departments,
        years=YEARS,
        sections=sections,
        selected_department=int(department_id) if department_id else None,
        selected_year=int(year) if year else None,
        selected_section=section,
    )


@app.route("/timetable/add", methods=["GET", "POST"])
@role_required("admin")
def add_timetable_entry():
    departments = db.get_all_departments()
    subjects = db.get_all_subjects()
    faculty = db.get_all_faculty()

    if request.method == "POST":
        department_id = request.form.get("department_id") or None
        year = request.form.get("year") or None
        section = request.form.get("section", "").strip()
        day_of_week = request.form.get("day_of_week", "").strip()
        hour = request.form.get("hour") or None
        subject_id = request.form.get("subject_id") or None
        faculty_id = request.form.get("faculty_id") or None

        if not all([department_id, year, section, day_of_week, hour, subject_id, faculty_id]):
            flash("All fields are required.", "error")
            return render_template("timetable_form.html", entry=None, action="Add",
                                    departments=departments, subjects=subjects, faculty=faculty,
                                    days=DAYS_OF_WEEK, years=YEARS, periods=PERIODS)
        try:
            db.add_timetable_entry(department_id, year, section, day_of_week, hour, subject_id, faculty_id)
            flash("Timetable entry added successfully.", "success")
            return redirect(url_for("timetable", department_id=department_id, year=year, section=section))
        except Exception as e:
            flash(f"Error adding timetable entry (slot may already be filled): {e}", "error")

    return render_template("timetable_form.html", entry=None, action="Add",
                            departments=departments, subjects=subjects, faculty=faculty,
                            days=DAYS_OF_WEEK, years=YEARS, periods=PERIODS)


@app.route("/timetable/edit/<int:entry_id>", methods=["GET", "POST"])
@role_required("admin")
def edit_timetable_entry(entry_id):
    entry = db.get_timetable_entry(entry_id)
    departments = db.get_all_departments()
    subjects = db.get_all_subjects()
    faculty = db.get_all_faculty()
    if not entry:
        flash("Timetable entry not found.", "error")
        return redirect(url_for("timetable"))

    if request.method == "POST":
        department_id = request.form.get("department_id") or None
        year = request.form.get("year") or None
        section = request.form.get("section", "").strip()
        day_of_week = request.form.get("day_of_week", "").strip()
        hour = request.form.get("hour") or None
        subject_id = request.form.get("subject_id") or None
        faculty_id = request.form.get("faculty_id") or None

        if not all([department_id, year, section, day_of_week, hour, subject_id, faculty_id]):
            flash("All fields are required.", "error")
            return render_template("timetable_form.html", entry=entry, action="Edit",
                                    departments=departments, subjects=subjects, faculty=faculty,
                                    days=DAYS_OF_WEEK, years=YEARS, periods=PERIODS)
        try:
            db.update_timetable_entry(entry_id, department_id, year, section, day_of_week,
                                       hour, subject_id, faculty_id)
            flash("Timetable entry updated successfully.", "success")
            return redirect(url_for("timetable", department_id=department_id, year=year, section=section))
        except Exception as e:
            flash(f"Error updating timetable entry: {e}", "error")

    return render_template("timetable_form.html", entry=entry, action="Edit",
                            departments=departments, subjects=subjects, faculty=faculty,
                            days=DAYS_OF_WEEK, years=YEARS, periods=PERIODS)


@app.route("/timetable/delete/<int:entry_id>", methods=["POST"])
@role_required("admin")
def delete_timetable_entry(entry_id):
    entry = db.get_timetable_entry(entry_id)
    if entry:
        db.delete_timetable_entry(entry_id)
        flash("Timetable entry deleted.", "success")
        return redirect(url_for("timetable", department_id=entry["department_id"],
                                 year=entry["year"], section=entry["section"]))
    return redirect(url_for("timetable"))


# =====================================================================
# ATTENDANCE MODULE (Faculty marks; subject auto-loaded from timetable)
# =====================================================================

@app.route("/attendance", methods=["GET", "POST"])
@role_required("admin", "faculty")
def attendance():
    departments = db.get_all_departments()

    department_id = request.values.get("department_id") or None
    year = request.values.get("year") or None
    section = request.values.get("section") or None
    selected_date = request.values.get("date") or date.today().isoformat()
    hour = request.values.get("hour") or None

    sections = db.get_distinct_sections(department_id, year) if department_id and year else []

    slot = None
    records = []
    day_name = None

    if department_id and year and section and selected_date and hour:
        try:
            day_name = datetime.strptime(selected_date, "%Y-%m-%d").strftime("%A")
        except ValueError:
            day_name = None

        if day_name:
            slot = db.find_timetable_slot(department_id, year, section, day_name, hour)

        if request.method == "POST":
            if not slot:
                flash("No subject is scheduled for that department/year/section/day/hour in the timetable.", "error")
            else:
                student_ids = request.form.getlist("student_id")
                for sid in student_ids:
                    status = request.form.get(f"status_{sid}")
                    if status in ("Present", "Absent"):
                        db.mark_attendance(int(sid), selected_date, int(hour),
                                            slot["subject_id"], slot["faculty_id"], status)
                flash(f"Attendance saved for {selected_date}, Hour {hour}.", "success")
                return redirect(url_for("attendance", department_id=department_id, year=year,
                                         section=section, date=selected_date, hour=hour))

        if slot:
            records = db.get_attendance_for_session(department_id, year, section, selected_date, hour)

    return render_template(
        "attendance.html",
        departments=departments,
        years=YEARS,
        periods=PERIODS,
        sections=sections,
        selected_department=int(department_id) if department_id else None,
        selected_year=int(year) if year else None,
        selected_section=section,
        selected_date=selected_date,
        selected_hour=int(hour) if hour else None,
        day_name=day_name,
        slot=slot,
        records=records,
    )


# =====================================================================
# REPORTS (Admin & Faculty)
# =====================================================================

@app.route("/reports")
@role_required("admin", "faculty")
def reports():
    report_type = request.args.get("type", "daily")
    departments = db.get_all_departments()
    subjects = db.get_all_subjects()
    students_all = db.get_all_students()

    context = {
        "report_type": report_type,
        "departments": departments,
        "subjects": subjects,
        "students_all": students_all,
        "years": YEARS,
    }

    if report_type == "daily":
        report_date = request.args.get("date") or date.today().isoformat()
        context["report_date"] = report_date
        context["rows"] = db.get_daily_report(report_date)

    elif report_type == "monthly":
        year_month = request.args.get("month") or date.today().strftime("%Y-%m")
        context["year_month"] = year_month
        context["rows"] = db.get_monthly_report(year_month)

    elif report_type == "student":
        student_id = request.args.get("student_id") or None
        context["selected_student_id"] = int(student_id) if student_id else None
        context["rows"] = db.get_student_wise_report(student_id)

    elif report_type == "subject":
        subject_id = request.args.get("subject_id") or None
        context["selected_subject_id"] = int(subject_id) if subject_id else None
        context["rows"] = db.get_subject_wise_report(subject_id)

    elif report_type == "department":
        department_id = request.args.get("department_id") or None
        context["selected_department_id"] = int(department_id) if department_id else None
        context["rows"] = db.get_department_wise_report(department_id)

    elif report_type == "year":
        year = request.args.get("year") or None
        context["selected_year"] = int(year) if year else None
        context["rows"] = db.get_year_wise_report(year)

    elif report_type == "section":
        section = request.args.get("section") or None
        context["selected_section"] = section
        context["sections"] = db.get_distinct_sections()
        context["rows"] = db.get_section_wise_report(section)

    elif report_type == "below75":
        context["rows"] = db.get_students_below_75()

    else:
        report_type = "daily"
        context["report_type"] = report_type
        context["report_date"] = date.today().isoformat()
        context["rows"] = db.get_daily_report(context["report_date"])

    return render_template("reports.html", **context)


@app.route("/reports/export")
@role_required("admin")
def export_csv():
    rows = db.get_all_attendance_rows()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Roll No", "Name", "Department", "Year", "Section", "Date", "Hour", "Subject", "Status"])
    for r in rows:
        writer.writerow([r["roll_no"], r["name"], r["department_name"], r["year"], r["section"],
                          r["date"], r["hour"], r["subject_name"], r["status"]])

    response = Response(output.getvalue(), mimetype="text/csv")
    filename = f"attendance_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    return response


# ---------- Entry point ----------

if __name__ == "__main__":
    # Flask's debug reloader re-executes this script in a child process
    # (setting WERKZEUG_RUN_MAIN=true in that child) while the original
    # process keeps running as a file-watcher. Without this guard,
    # db.init_db() would run twice at startup - once in the watcher
    # process and once in the reloaded child - and those two runs could
    # overlap and contend for the same SQLite write lock, which is what
    # produced the "database is locked" error on the
    # "INSERT OR REPLACE INTO schema_info" statement. Running init_db()
    # only in the watcher process (before the reloader forks the child)
    # keeps initialization to a single call without disabling the
    # reloader or losing debug auto-reload behavior.
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        db.init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
