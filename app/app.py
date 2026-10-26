from datetime import date
import sqlite3
import time
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

from app.database import get_db_connection, init_db

app = Flask(__name__)
app.secret_key = "attendance-devops-secret-key-for-session"

# ================= Prometheus Metrics =================
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the application",
    ["method", "endpoint", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"]
)
STUDENTS_COUNT_GAUGE = Gauge(
    "attendance_students_total",
    "Total number of registered students in the system"
)
ATTENDANCE_ENTRIES_COUNT = Counter(
    "attendance_entries_marked_total",
    "Total attendance entries recorded (Present or Absent)",
    ["status"]
)


def update_student_gauge():
    """Update gauge metric with current student count."""
    try:
        conn = get_db_connection()
        count = conn.execute("SELECT COUNT(*) AS total FROM students").fetchone()["total"]
        conn.close()
        STUDENTS_COUNT_GAUGE.set(count)
    except Exception:
        pass


@app.before_request
def start_timer():
    request._start_time = time.time()


@app.after_request
def record_metrics(response):
    if hasattr(request, "_start_time"):
        latency = time.time() - request._start_time
        endpoint = request.endpoint or "unknown"
        HTTP_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(latency)
        HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            endpoint=endpoint,
            status=response.status_code
        ).inc()
    return response


# ================= Health & Metrics Routes =================
@app.route("/healthz")
def healthz():
    """Liveness/Readiness probe endpoint for Kubernetes and Docker healthchecks."""
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1").fetchone()
        conn.close()
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


@app.route("/metrics")
def metrics():
    """Prometheus metrics scraping endpoint."""
    update_student_gauge()
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)


# ================= Application Routes =================
@app.route("/")
def index():
    """Dashboard overview: summary counts and quick links."""
    conn = get_db_connection()
    today_str = date.today().isoformat()

    total_students = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    
    today_attendance = conn.execute("""
        SELECT 
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present_count,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent_count,
            COUNT(*) AS total_marked
        FROM attendance 
        WHERE date = ?
    """, (today_str,)).fetchone()

    present_count = today_attendance["present_count"] or 0
    absent_count = today_attendance["absent_count"] or 0
    total_marked = today_attendance["total_marked"] or 0

    recent_attendance = conn.execute("""
        SELECT a.date, a.status, s.roll_no, s.name
        FROM attendance a
        JOIN students s ON a.student_id = s.id
        ORDER BY a.recorded_at DESC
        LIMIT 5
    """).fetchall()

    conn.close()
    return render_template(
        "index.html",
        total_students=total_students,
        today=today_str,
        present_count=present_count,
        absent_count=absent_count,
        total_marked=total_marked,
        recent_attendance=recent_attendance
    )


@app.route("/students", methods=["GET", "POST"])
def students():
    """Add student and view student list."""
    conn = get_db_connection()

    if request.method == "POST":
        roll_no = request.form.get("roll_no", "").strip()
        name = request.form.get("name", "").strip()

        # Validation
        if not roll_no or not name:
            flash("Both Roll Number and Name are required.", "danger")
        elif len(roll_no) > 20:
            flash("Roll Number must not exceed 20 characters.", "danger")
        elif len(name) > 100:
            flash("Student Name must not exceed 100 characters.", "danger")
        else:
            try:
                conn.execute(
                    "INSERT INTO students (roll_no, name) VALUES (?, ?)",
                    (roll_no, name)
                )
                conn.commit()
                flash(f"Student '{name}' (Roll No: {roll_no}) added successfully!", "success")
                conn.close()
                return redirect(url_for("students"))
            except sqlite3.IntegrityError:
                flash(f"Roll Number '{roll_no}' already exists. Please use a unique roll number.", "danger")
            except Exception as e:
                flash(f"Database error: {str(e)}", "danger")

    student_list = conn.execute("SELECT id, roll_no, name, created_at FROM students ORDER BY roll_no ASC").fetchall()
    conn.close()
    return render_template("students.html", students=student_list)


@app.route("/attendance/mark", methods=["GET", "POST"])
def mark_attendance():
    """Mark Present or Absent for all students on a selected date."""
    conn = get_db_connection()
    selected_date = request.args.get("date") or request.form.get("date") or date.today().isoformat()

    # Validate date format (YYYY-MM-DD)
    try:
        parsed_date = date.fromisoformat(selected_date)
        selected_date = parsed_date.isoformat()
    except ValueError:
        flash("Invalid date format. Please use YYYY-MM-DD.", "danger")
        selected_date = date.today().isoformat()

    if request.method == "POST":
        # Form inputs are named "status_<student_id>"
        student_records = conn.execute("SELECT id FROM students").fetchall()
        updated_count = 0

        for student in student_records:
            field_name = f"status_{student['id']}"
            status = request.form.get(field_name)
            if status in ("Present", "Absent"):
                conn.execute("""
                    INSERT INTO attendance (student_id, date, status)
                    VALUES (?, ?, ?)
                    ON CONFLICT(student_id, date) DO UPDATE SET
                        status = excluded.status,
                        recorded_at = CURRENT_TIMESTAMP
                """, (student["id"], selected_date, status))
                ATTENDANCE_ENTRIES_COUNT.labels(status=status).inc()
                updated_count += 1

        conn.commit()
        if updated_count > 0:
            flash(f"Attendance recorded for {updated_count} student(s) on {selected_date}.", "success")
        else:
            flash("No students were selected for attendance update.", "warning")
        conn.close()
        return redirect(url_for("mark_attendance", date=selected_date))

    # GET request: load all students and their current status for the date if any
    students_with_status = conn.execute("""
        SELECT 
            s.id, 
            s.roll_no, 
            s.name, 
            a.status
        FROM students s
        LEFT JOIN attendance a ON s.id = a.student_id AND a.date = ?
        ORDER BY s.roll_no ASC
    """, (selected_date,)).fetchall()
    conn.close()

    return render_template(
        "mark_attendance.html",
        students=students_with_status,
        selected_date=selected_date
    )


@app.route("/attendance/records")
def attendance_records():
    """View attendance records with optional date filtering."""
    selected_date = request.args.get("date", "").strip()
    conn = get_db_connection()

    if selected_date:
        records = conn.execute("""
            SELECT a.id, s.roll_no, s.name, a.date, a.status, a.recorded_at
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            WHERE a.date = ?
            ORDER BY s.roll_no ASC
        """, (selected_date,)).fetchall()
    else:
        records = conn.execute("""
            SELECT a.id, s.roll_no, s.name, a.date, a.status, a.recorded_at
            FROM attendance a
            JOIN students s ON a.student_id = s.id
            ORDER BY a.date DESC, s.roll_no ASC
            LIMIT 100
        """).fetchall()

    conn.close()
    return render_template(
        "attendance_records.html",
        records=records,
        selected_date=selected_date
    )


# Ensure DB is created on startup
with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
