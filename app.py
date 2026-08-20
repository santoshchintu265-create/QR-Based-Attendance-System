from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import uuid
import qrcode
import os


app = Flask(__name__)

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///attendance.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)


# ============================================================
# Configuration
# ============================================================

# IMPORTANT:
# Replace this with the IPv4 address of the computer running Flask.
# Your previous screenshot showed 10.199.217.216.
SERVER_IP = "10.199.217.216"
SERVER_PORT = 5000


# ============================================================
# Database Models
# ============================================================

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100), nullable=False)
    roll_number = db.Column(db.String(50), unique=True, nullable=False)

    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    department = db.Column(db.String(100))
    semester = db.Column(db.String(50))

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Active"
    )

    attendances = db.relationship(
        "Attendance",
        backref="student",
        lazy=True,
        cascade="all, delete-orphan"
    )


class AttendanceSession(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    session_token = db.Column(
        db.String(100),
        unique=True,
        nullable=False,
        index=True
    )

    subject = db.Column(
        db.String(150),
        nullable=False
    )

    semester = db.Column(
        db.String(50),
        nullable=False
    )

    section = db.Column(
        db.String(50),
        nullable=False
    )

    expires_at = db.Column(
        db.DateTime,
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    attendances = db.relationship(
        "Attendance",
        backref="session",
        lazy=True,
        cascade="all, delete-orphan"
    )


class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id"),
        nullable=False
    )

    session_id = db.Column(
        db.Integer,
        db.ForeignKey("attendance_session.id"),
        nullable=False
    )

    scanned_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="Present"
    )


# ============================================================
# Helper Functions
# ============================================================

def get_active_students():
    return Student.query.filter_by(status="Active").order_by(
        Student.roll_number.asc()
    ).all()


def get_session_lists(session):
    """Return present and absent students for one attendance session."""

    students = Student.query.filter_by(
        semester=session.semester,
        status="Active"
    ).order_by(Student.roll_number.asc()).all()

    records = Attendance.query.filter_by(
        session_id=session.id,
        status="Present"
    ).all()

    present_ids = {record.student_id for record in records}

    present_students = [
        student for student in students
        if student.id in present_ids
    ]

    absent_students = [
        student for student in students
        if student.id not in present_ids
    ]

    return present_students, absent_students


def session_statistics(session):
    """Return total, present, absent and percentage for a session."""

    total = Student.query.filter_by(
        semester=session.semester,
        status="Active"
    ).count()

    present = Attendance.query.filter_by(
        session_id=session.id,
        status="Present"
    ).count()

    absent = max(total - present, 0)

    percentage = (
        (present / total) * 100
        if total
        else 0
    )

    return {
        "total": total,
        "present": present,
        "absent": absent,
        "percentage": round(percentage, 2)
    }


def student_attendance_percentage(student_id):
    """Calculate attendance percentage across all sessions for a student."""

    total_sessions = AttendanceSession.query.count()

    present_sessions = Attendance.query.filter_by(
        student_id=student_id,
        status="Present"
    ).count()

    if total_sessions == 0:
        return 0

    return round(
        (present_sessions / total_sessions) * 100,
        2
    )


def ensure_session_active(session):
    """Automatically deactivate an expired session."""

    if session.is_active and datetime.utcnow() > session.expires_at:
        session.is_active = False
        db.session.commit()

    return session.is_active


def make_scan_url(token):
    return (
        f"http://{SERVER_IP}:{SERVER_PORT}"
        f"/scan/{token}"
    )


# ============================================================
# Dashboard
# ============================================================

@app.route("/")
def dashboard():

    session = AttendanceSession.query.order_by(
        AttendanceSession.id.desc()
    ).first()

    total_students = Student.query.filter_by(
        status="Active"
    ).count()

    present_students = []
    absent_students = []
    present_count = 0
    absent_count = total_students
    percentage = 0

    if session:
        ensure_session_active(session)

        present_students, absent_students = get_session_lists(
            session
        )

        stats = session_statistics(session)

        present_count = stats["present"]
        absent_count = stats["absent"]
        percentage = stats["percentage"]

    return render_template(
        "dashboard.html",
        session=session,
        total_students=total_students,
        present_students=present_students,
        absent_students=absent_students,
        present_count=present_count,
        absent_count=absent_count,
        percentage=percentage
    )


# ============================================================
# Student Management
# ============================================================

@app.route("/students")
def students():

    search = request.args.get(
        "search",
        ""
    ).strip()

    query = Student.query

    if search:
        pattern = f"%{search}%"

        query = query.filter(
            db.or_(
                Student.name.ilike(pattern),
                Student.roll_number.ilike(pattern),
                Student.email.ilike(pattern),
                Student.department.ilike(pattern)
            )
        )

    student_list = query.order_by(
        Student.roll_number.asc()
    ).all()

    return render_template(
        "students.html",
        students=student_list,
        search=search
    )


@app.route(
    "/add-student",
    methods=["GET", "POST"]
)
def add_student():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        roll_number = request.form.get(
            "roll_number",
            ""
        ).strip()

        email = request.form.get(
            "email",
            ""
        ).strip()

        phone = request.form.get(
            "phone",
            ""
        ).strip()

        department = request.form.get(
            "department",
            ""
        ).strip()

        semester = request.form.get(
            "semester",
            ""
        ).strip()

        if not name or not roll_number:
            return "Name and roll number are required.", 400

        existing = Student.query.filter_by(
            roll_number=roll_number
        ).first()

        if existing:
            return "Roll number already exists.", 409

        student = Student(
            name=name,
            roll_number=roll_number,
            email=email,
            phone=phone,
            department=department,
            semester=semester,
            status="Active"
        )

        db.session.add(student)
        db.session.commit()

        return redirect(
            url_for("students")
        )

    return render_template(
        "add_student.html"
    )


@app.route(
    "/students/edit/<int:student_id>",
    methods=["GET", "POST"]
)
def edit_student(student_id):

    student = Student.query.get_or_404(
        student_id
    )

    if request.method == "POST":

        new_roll = request.form.get(
            "roll_number",
            ""
        ).strip()

        duplicate = Student.query.filter(
            Student.roll_number == new_roll,
            Student.id != student.id
        ).first()

        if duplicate:
            return "Roll number already exists.", 409

        student.name = request.form.get(
            "name",
            ""
        ).strip()

        student.roll_number = new_roll

        student.email = request.form.get(
            "email",
            ""
        ).strip()

        student.phone = request.form.get(
            "phone",
            ""
        ).strip()

        student.department = request.form.get(
            "department",
            ""
        ).strip()

        student.semester = request.form.get(
            "semester",
            ""
        ).strip()

        student.status = request.form.get(
            "status",
            "Active"
        )

        db.session.commit()

        return redirect(
            url_for("students")
        )

    return render_template(
        "edit_student.html",
        student=student
    )


@app.route(
    "/students/delete/<int:student_id>",
    methods=["POST"]
)
def delete_student(student_id):

    student = Student.query.get_or_404(
        student_id
    )

    db.session.delete(student)
    db.session.commit()

    return redirect(
        url_for("students")
    )


# ============================================================
# Start Attendance
# ============================================================

@app.route(
    "/start-attendance",
    methods=["GET", "POST"]
)
def start_attendance():

    if request.method == "GET":
        return render_template(
            "start_attendance.html"
        )

    subject = request.form.get(
        "subject",
        ""
    ).strip()

    semester = request.form.get(
        "semester",
        ""
    ).strip()

    section = request.form.get(
        "section",
        ""
    ).strip()

    try:
        validity = int(
            request.form.get(
                "validity",
                5
            )
        )
    except ValueError:
        validity = 5

    allowed_validity = {
        2,
        5,
        10,
        15,
        30
    }

    if validity not in allowed_validity:
        validity = 5

    if not subject or not semester or not section:
        return (
            "Subject, semester and section are required.",
            400
        )

    # End previous active sessions.
    active_sessions = AttendanceSession.query.filter_by(
        is_active=True
    ).all()

    for active_session in active_sessions:
        active_session.is_active = False

    token = str(uuid.uuid4())

    expires_at = datetime.utcnow() + timedelta(
        minutes=validity
    )

    session = AttendanceSession(
        session_token=token,
        subject=subject,
        semester=semester,
        section=section,
        expires_at=expires_at,
        is_active=True
    )

    db.session.add(session)
    db.session.commit()

    qr_directory = os.path.join(
        app.static_folder,
        "qrcodes"
    )

    os.makedirs(
        qr_directory,
        exist_ok=True
    )

    scan_url = make_scan_url(token)

    qr = qrcode.make(scan_url)

    qr_path = os.path.join(
        qr_directory,
        f"{token}.png"
    )

    qr.save(qr_path)

    return redirect(
        url_for(
            "show_qr",
            token=token
        )
    )


# ============================================================
# Show QR
# ============================================================

@app.route("/qr/<token>")
def show_qr(token):

    session = AttendanceSession.query.filter_by(
        session_token=token
    ).first_or_404()

    ensure_session_active(session)

    stats = session_statistics(session)

    return render_template(
        "qr.html",
        token=token,
        session=session,
        attendance_count=stats["present"],
        total_students=stats["total"],
        present_count=stats["present"],
        absent_count=stats["absent"],
        percentage=stats["percentage"]
    )


# ============================================================
# Student Scan
# ============================================================

@app.route(
    "/scan/<token>",
    methods=["GET", "POST"]
)
def scan(token):

    session = AttendanceSession.query.filter_by(
        session_token=token
    ).first()

    if not session:
        return "Invalid attendance QR code.", 404

    if not ensure_session_active(session):
        return """
            <h1>Attendance Session Ended</h1>
            <p>This QR code is no longer active.</p>
        """, 410

    if request.method == "POST":

        roll_number = request.form.get(
            "roll_number",
            ""
        ).strip()

        student = Student.query.filter_by(
            roll_number=roll_number,
            status="Active"
        ).first()

        if not student:
            return """
                <h1>Student Not Found</h1>
                <p>Please check your roll number.</p>
            """, 404

        # Student must belong to the session semester.
        if (
            student.semester
            and student.semester != session.semester
        ):
            return """
                <h1>Invalid Student</h1>
                <p>
                    This student does not belong to
                    the selected semester.
                </p>
            """, 403

        existing = Attendance.query.filter_by(
            student_id=student.id,
            session_id=session.id
        ).first()

        if existing:
            return """
                <h1>Already Marked</h1>
                <p>
                    Your attendance has already
                    been recorded.
                </p>
            """

        attendance = Attendance(
            student_id=student.id,
            session_id=session.id,
            status="Present"
        )

        db.session.add(attendance)
        db.session.commit()

        return """
            <h1>Attendance Recorded</h1>
            <p>
                Your attendance has been
                successfully marked.
            </p>
        """

    stats = session_statistics(session)

    return render_template(
        "scan.html",
        token=token,
        session=session,
        attendance_count=stats["present"],
        total_students=stats["total"],
        percentage=stats["percentage"]
    )


# ============================================================
# Attendance Page
# ============================================================

@app.route("/attendance")
def attendance():

    date_filter = request.args.get(
        "date",
        ""
    ).strip()

    subject_filter = request.args.get(
        "subject",
        ""
    ).strip()

    semester_filter = request.args.get(
        "semester",
        ""
    ).strip()

    section_filter = request.args.get(
        "section",
        ""
    ).strip()

    query = Attendance.query.join(
        AttendanceSession
    ).join(
        Student
    )

    if date_filter:
        try:
            selected_date = datetime.strptime(
                date_filter,
                "%Y-%m-%d"
            ).date()

            query = query.filter(
                db.func.date(
                    Attendance.scanned_at
                ) == selected_date
            )
        except ValueError:
            pass

    if subject_filter:
        query = query.filter(
            AttendanceSession.subject ==
            subject_filter
        )

    if semester_filter:
        query = query.filter(
            AttendanceSession.semester ==
            semester_filter
        )

    if section_filter:
        query = query.filter(
            AttendanceSession.section ==
            section_filter
        )

    records = query.order_by(
        Attendance.scanned_at.desc()
    ).all()

    subjects = [
        row[0]
        for row in db.session.query(
            AttendanceSession.subject
        ).distinct().order_by(
            AttendanceSession.subject
        ).all()
    ]

    semesters = [
        row[0]
        for row in db.session.query(
            AttendanceSession.semester
        ).distinct().order_by(
            AttendanceSession.semester
        ).all()
    ]

    sections = [
        row[0]
        for row in db.session.query(
            AttendanceSession.section
        ).distinct().order_by(
            AttendanceSession.section
        ).all()
    ]

    return render_template(
        "attendance.html",
        records=records,
        subjects=subjects,
        semesters=semesters,
        sections=sections,
        date_filter=date_filter,
        selected_subject=subject_filter,
        selected_semester=semester_filter,
        selected_section=section_filter
    )


# ============================================================
# End Attendance Session
# ============================================================

@app.route(
    "/attendance/end/<int:session_id>",
    methods=["POST"]
)
def end_attendance(session_id):

    session = AttendanceSession.query.get_or_404(
        session_id
    )

    session.is_active = False

    db.session.commit()

    return redirect(
        url_for("dashboard")
    )


# ============================================================
# Reports
# ============================================================

@app.route("/reports")
def reports():

    students = Student.query.filter_by(
        status="Active"
    ).order_by(
        Student.roll_number.asc()
    ).all()

    total_sessions = AttendanceSession.query.count()

    report_rows = []

    for student in students:

        present_count = Attendance.query.filter_by(
            student_id=student.id,
            status="Present"
        ).count()

        percentage = (
            (present_count / total_sessions) * 100
            if total_sessions
            else 0
        )

        report_rows.append({
            "student": student,
            "present": present_count,
            "total": total_sessions,
            "percentage": round(
                percentage,
                2
            )
        })

    return render_template(
        "reports.html",
        reports=report_rows,
        total_students=len(students),
        total_sessions=total_sessions
    )


# ============================================================
# JSON API - Useful for AJAX/live dashboard
# ============================================================

@app.route(
    "/api/session/<int:session_id>"
)
def session_api(session_id):

    session = AttendanceSession.query.get_or_404(
        session_id
    )

    ensure_session_active(session)

    stats = session_statistics(session)

    present_students, absent_students = (
        get_session_lists(session)
    )

    return jsonify({
        "session": {
            "id": session.id,
            "subject": session.subject,
            "semester": session.semester,
            "section": session.section,
            "is_active": session.is_active,
            "created_at": session.created_at.isoformat(),
            "expires_at": session.expires_at.isoformat()
        },
        "statistics": stats,
        "present_students": [
            {
                "id": student.id,
                "name": student.name,
                "roll_number": student.roll_number
            }
            for student in present_students
        ],
        "absent_students": [
            {
                "id": student.id,
                "name": student.name,
                "roll_number": student.roll_number
            }
            for student in absent_students
        ]
    })


# ============================================================
# Database Initialization
# ============================================================

with app.app_context():
    db.create_all()


# ============================================================
# Run Application
# ============================================================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=SERVER_PORT,
        debug=True
    )
