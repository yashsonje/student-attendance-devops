import os
import pytest
from app.app import app
from app.database import init_db, get_db_connection

@pytest.fixture
def client(tmp_path, monkeypatch):
    """Set up an isolated temporary database and Flask test client."""
    test_db = str(tmp_path / "test_attendance.db")
    monkeypatch.setenv("DATABASE_PATH", test_db)
    
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        init_db(test_db)

    with app.test_client() as client:
        yield client


def test_healthz_endpoint(client):
    """Test health check probe."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


def test_metrics_endpoint(client):
    """Test Prometheus metrics endpoint."""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert b"http_requests_total" in response.data
    assert b"attendance_students_total" in response.data


def test_dashboard_page(client):
    """Test dashboard overview page loads successfully."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Dashboard Overview" in response.data
    assert b"Total Registered Students" in response.data


def test_students_page_get(client):
    """Test student management page loads."""
    response = client.get("/students")
    assert response.status_code == 200
    assert b"Manage Students" in response.data
    assert b"No students registered yet" in response.data


def test_add_student_success(client):
    """Test successfully adding a student."""
    response = client.post("/students", data={
        "roll_no": "CS2026-001",
        "name": "Alice Smith"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Alice Smith" in response.data
    assert b"CS2026-001" in response.data
    assert b"added successfully" in response.data


def test_add_student_validation_empty_fields(client):
    """Test validation when fields are empty."""
    response = client.post("/students", data={
        "roll_no": "",
        "name": ""
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Both Roll Number and Name are required" in response.data


def test_add_student_duplicate_roll_no(client):
    """Test error handling when roll number already exists."""
    # First student
    client.post("/students", data={"roll_no": "CS-101", "name": "Bob"}, follow_redirects=True)
    # Duplicate student
    response = client.post("/students", data={"roll_no": "CS-101", "name": "Charlie"}, follow_redirects=True)

    assert response.status_code == 200
    assert b"already exists" in response.data


def test_mark_attendance_flow(client):
    """Test marking attendance for registered students."""
    # Register 2 students
    client.post("/students", data={"roll_no": "CS-001", "name": "Student One"}, follow_redirects=True)
    client.post("/students", data={"roll_no": "CS-002", "name": "Student Two"}, follow_redirects=True)

    # Get student IDs
    conn = get_db_connection()
    students = conn.execute("SELECT id, roll_no FROM students ORDER BY roll_no").fetchall()
    conn.close()

    s1_id = students[0]["id"]
    s2_id = students[1]["id"]

    # Mark attendance for date 2026-10-26
    response = client.post("/attendance/mark", data={
        "date": "2026-10-26",
        f"status_{s1_id}": "Present",
        f"status_{s2_id}": "Absent"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Attendance recorded for 2 student(s)" in response.data

    # View records page
    records_response = client.get("/attendance/records?date=2026-10-26")
    assert records_response.status_code == 200
    assert b"Present" in records_response.data
    assert b"Absent" in records_response.data
    assert b"Student One" in records_response.data
    assert b"Student Two" in records_response.data


def test_update_existing_attendance(client):
    """Test updating existing attendance on the same date (upsert)."""
    client.post("/students", data={"roll_no": "CS-999", "name": "Eve"}, follow_redirects=True)

    conn = get_db_connection()
    eve = conn.execute("SELECT id FROM students WHERE roll_no = 'CS-999'").fetchone()
    conn.close()

    # Mark Absent first
    client.post("/attendance/mark", data={
        "date": "2026-10-26",
        f"status_{eve['id']}": "Absent"
    }, follow_redirects=True)

    # Change to Present
    client.post("/attendance/mark", data={
        "date": "2026-10-26",
        f"status_{eve['id']}": "Present"
    }, follow_redirects=True)

    # Verify only 1 record exists and status is Present
    conn = get_db_connection()
    records = conn.execute(
        "SELECT status FROM attendance WHERE student_id = ? AND date = ?", 
        (eve["id"], "2026-10-26")
    ).fetchall()
    conn.close()

    assert len(records) == 1
    assert records[0]["status"] == "Present"
