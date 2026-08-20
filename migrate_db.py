import sqlite3
import os


DB_PATH = os.path.join(
    "instance",
    "attendance.db"
)


def get_columns(cursor, table_name):
    cursor.execute(
        f"PRAGMA table_info({table_name})"
    )

    return {
        row[1]
        for row in cursor.fetchall()
    }


connection = sqlite3.connect(DB_PATH)
cursor = connection.cursor()


# ============================================================
# attendance_session
# ============================================================

session_columns = get_columns(
    cursor,
    "attendance_session"
)

print("Existing attendance_session columns:")
print(session_columns)


if "subject" not in session_columns:
    print("Adding subject...")
    cursor.execute(
        """
        ALTER TABLE attendance_session
        ADD COLUMN subject VARCHAR(150)
        """
    )


if "semester" not in session_columns:
    print("Adding semester...")
    cursor.execute(
        """
        ALTER TABLE attendance_session
        ADD COLUMN semester VARCHAR(50)
        """
    )


if "section" not in session_columns:
    print("Adding section...")
    cursor.execute(
        """
        ALTER TABLE attendance_session
        ADD COLUMN section VARCHAR(50)
        """
    )


if "expires_at" not in session_columns:
    print("Adding expires_at...")
    cursor.execute(
        """
        ALTER TABLE attendance_session
        ADD COLUMN expires_at DATETIME
        """
    )


if "created_at" not in session_columns:
    print("Adding created_at...")
    cursor.execute(
        """
        ALTER TABLE attendance_session
        ADD COLUMN created_at DATETIME
        """
    )


if "is_active" not in session_columns:
    print("Adding is_active...")
    cursor.execute(
        """
        ALTER TABLE attendance_session
        ADD COLUMN is_active BOOLEAN DEFAULT 1
        """
    )


# ============================================================
# student
# ============================================================

student_columns = get_columns(
    cursor,
    "student"
)

print("\nExisting student columns:")
print(student_columns)


if "email" not in student_columns:
    print("Adding student.email...")
    cursor.execute(
        """
        ALTER TABLE student
        ADD COLUMN email VARCHAR(120)
        """
    )


if "phone" not in student_columns:
    print("Adding student.phone...")
    cursor.execute(
        """
        ALTER TABLE student
        ADD COLUMN phone VARCHAR(20)
        """
    )


if "department" not in student_columns:
    print("Adding student.department...")
    cursor.execute(
        """
        ALTER TABLE student
        ADD COLUMN department VARCHAR(100)
        """
    )


if "semester" not in student_columns:
    print("Adding student.semester...")
    cursor.execute(
        """
        ALTER TABLE student
        ADD COLUMN semester VARCHAR(50)
        """
    )


if "status" not in student_columns:
    print("Adding student.status...")
    cursor.execute(
        """
        ALTER TABLE student
        ADD COLUMN status VARCHAR(20)
        DEFAULT 'Active'
        """
    )


# ============================================================
# attendance
# ============================================================

attendance_columns = get_columns(
    cursor,
    "attendance"
)

print("\nExisting attendance columns:")
print(attendance_columns)


if "scanned_at" not in attendance_columns:
    print("Adding attendance.scanned_at...")
    cursor.execute(
        """
        ALTER TABLE attendance
        ADD COLUMN scanned_at DATETIME
        """
    )


if "status" not in attendance_columns:
    print("Adding attendance.status...")
    cursor.execute(
        """
        ALTER TABLE attendance
        ADD COLUMN status VARCHAR(20)
        DEFAULT 'Present'
        """
    )


connection.commit()
connection.close()


print("\n================================")
print("DATABASE MIGRATION COMPLETE")
print("================================")