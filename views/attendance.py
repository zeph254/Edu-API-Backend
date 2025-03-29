from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, date
from models import db, AttendanceSession, AttendanceRecord, Class, Subject, Student, User
from sqlalchemy.exc import IntegrityError

attendance_bp = Blueprint('attendance', __name__)

# Helper functions
def validate_attendance_session_data(data):
    errors = {}
    
    required_fields = ['date', 'recorded_by']
    for field in required_fields:
        if field not in data:
            errors[field] = f"{field.replace('_', ' ').title()} is required"
    
    if 'date' in data:
        try:
            datetime.strptime(data['date'], '%Y-%m-%d')
        except ValueError:
            errors['date'] = "Invalid date format (YYYY-MM-DD)"
    
    if 'class_id' in data and not Class.query.get(data['class_id']):
        errors['class_id'] = "Class not found"
    
    if 'subject_id' in data and not Subject.query.get(data['subject_id']):
        errors['subject_id'] = "Subject not found"
    
    if 'recorded_by' in data and not User.query.get(data['recorded_by']):
        errors['recorded_by'] = "User not found"
    
    return errors if errors else None

def validate_attendance_records_data(records, session_class_id):
    errors = []
    
    for i, record in enumerate(records):
        if 'student_id' not in record:
            errors.append(f"Record {i}: Missing student_id")
            continue
            
        student = Student.query.get(record['student_id'])
        if not student:
            errors.append(f"Record {i}: Student not found")
        elif student.class_id != session_class_id:
            errors.append(f"Record {i}: Student doesn't belong to this class")
            
        if 'status' not in record:
            errors.append(f"Record {i}: Missing status")
        elif record['status'] not in ['present', 'absent', 'late', 'excused']:
            errors.append(f"Record {i}: Invalid status")
    
    return errors if errors else None

@attendance_bp.route('/attendance/sessions', methods=['POST'])
@jwt_required()
def create_attendance_session():
    """Create a new attendance session with records"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only teachers, headteachers, and admin can record attendance
    if current_user.role not in ['teacher', 'headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    # Validate session data
    session_data = {
        'date': data.get('date'),
        'period': data.get('period'),
        'class_id': data.get('class_id'),
        'subject_id': data.get('subject_id'),
        'recorded_by': current_user_id,
        'is_school_wide': data.get('is_school_wide', False)
    }
    
    validation_errors = validate_attendance_session_data(session_data)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
    
    # Validate attendance records
    records = data.get('records', [])
    class_id = session_data['class_id']
    
    if not records:
        return jsonify({"error": "No attendance records provided"}), 400
    
    records_errors = validate_attendance_records_data(records, class_id)
    if records_errors:
        return jsonify({"error": "Records validation failed", "details": records_errors}), 400
    
    try:
        # Create attendance session
        new_session = AttendanceSession(
            date=datetime.strptime(session_data['date'], '%Y-%m-%d').date(),
            period=session_data.get('period'),
            class_id=session_data.get('class_id'),
            subject_id=session_data.get('subject_id'),
            recorded_by=session_data['recorded_by'],
            is_school_wide=session_data['is_school_wide']
        )
        
        db.session.add(new_session)
        db.session.flush()  # To get the session ID
        
        # Create attendance records
        for record_data in records:
            new_record = AttendanceRecord(
                status=record_data['status'],
                remarks=record_data.get('remarks'),
                session_id=new_session.id,
                student_id=record_data['student_id']
            )
            db.session.add(new_record)
        
        db.session.commit()
        
        return jsonify({
            "message": "Attendance session created successfully",
            "session_id": new_session.id
        }), 201
    
    except IntegrityError as e:
        db.session.rollback()
        return jsonify({"error": "Database integrity error", "details": str(e)}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@attendance_bp.route('/attendance/sessions/<int:session_id>', methods=['GET'])
@jwt_required()
def get_attendance_session(session_id):
    """Get a specific attendance session with all records"""
    session = AttendanceSession.query.get_or_404(session_id)
    
    # Get class and subject details if they exist
    class_details = None
    if session.class_id:
        class_ = Class.query.get(session.class_id)
        class_details = {
            "id": class_.id,
            "name": class_.name,
            "stream": class_.stream
        }
    
    subject_details = None
    if session.subject_id:
        subject = Subject.query.get(session.subject_id)
        subject_details = {
            "id": subject.id,
            "name": subject.name,
            "code": subject.code
        }
    
    # Get all records for this session
    records = AttendanceRecord.query.filter_by(session_id=session_id).all()
    records_data = []
    
    for record in records:
        student = Student.query.get(record.student_id)
        records_data.append({
            "id": record.id,
            "student_id": record.student_id,
            "student_name": student.full_name,
            "admission_number": student.admission_number,
            "status": record.status,
            "remarks": record.remarks
        })
    
    return jsonify({
        "session": {
            "id": session.id,
            "date": session.date.isoformat(),
            "period": session.period,
            "is_school_wide": session.is_school_wide,
            "class": class_details,
            "subject": subject_details,
            "recorded_by": User.query.get(session.recorded_by).full_name,
            "recorded_at": session.created_at.isoformat() if session.created_at else None
        },
        "records": records_data
    }), 200

@attendance_bp.route('/attendance/class/<int:class_id>', methods=['GET'])
@jwt_required()
def get_class_attendance(class_id):
    """Get all attendance sessions for a specific class"""
    class_ = Class.query.get_or_404(class_id)
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    
    query = AttendanceSession.query.filter_by(class_id=class_id)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(AttendanceSession.date >= date_from)
        except ValueError:
            return jsonify({"error": "Invalid date format for 'from' parameter (YYYY-MM-DD)"}), 400
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(AttendanceSession.date <= date_to)
        except ValueError:
            return jsonify({"error": "Invalid date format for 'to' parameter (YYYY-MM-DD)"}), 400
    
    sessions = query.order_by(AttendanceSession.date.desc()).all()
    
    sessions_data = []
    for session in sessions:
        subject = Subject.query.get(session.subject_id) if session.subject_id else None
        sessions_data.append({
            "id": session.id,
            "date": session.date.isoformat(),
            "period": session.period,
            "subject": {
                "id": subject.id if subject else None,
                "name": subject.name if subject else None
            },
            "recorded_by": User.query.get(session.recorded_by).full_name,
            "total_students": AttendanceRecord.query.filter_by(session_id=session.id).count(),
            "present_count": AttendanceRecord.query.filter_by(session_id=session.id, status='present').count()
        })
    
    return jsonify({
        "class": {
            "id": class_.id,
            "name": class_.name,
            "stream": class_.stream
        },
        "attendance_sessions": sessions_data
    }), 200

@attendance_bp.route('/attendance/student/<int:student_id>', methods=['GET'])
@jwt_required()
def get_student_attendance(student_id):
    """Get attendance history for a specific student"""
    student = Student.query.get_or_404(student_id)
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    
    query = AttendanceRecord.query.filter_by(student_id=student_id).join(AttendanceSession)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            query = query.filter(AttendanceSession.date >= date_from)
        except ValueError:
            return jsonify({"error": "Invalid date format for 'from' parameter (YYYY-MM-DD)"}), 400
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            query = query.filter(AttendanceSession.date <= date_to)
        except ValueError:
            return jsonify({"error": "Invalid date format for 'to' parameter (YYYY-MM-DD)"}), 400
    
    records = query.order_by(AttendanceSession.date.desc()).all()
    
    attendance_data = []
    for record in records:
        session = record.session
        subject = Subject.query.get(session.subject_id) if session.subject_id else None
        attendance_data.append({
            "date": session.date.isoformat(),
            "period": session.period,
            "status": record.status,
            "remarks": record.remarks,
            "subject": {
                "id": subject.id if subject else None,
                "name": subject.name if subject else None
            } if subject else None,
            "is_school_wide": session.is_school_wide,
            "recorded_by": User.query.get(session.recorded_by).full_name
        })
    
    # Calculate attendance statistics
    total_records = len(records)
    present_count = len([r for r in records if r.status == 'present'])
    attendance_rate = (present_count / total_records * 100) if total_records > 0 else 0
    
    return jsonify({
        "student": {
            "id": student.id,
            "name": student.full_name,
            "admission_number": student.admission_number,
            "class": {
                "id": student.class_.id,
                "name": student.class_.name
            }
        },
        "attendance_records": attendance_data,
        "statistics": {
            "total_days": total_records,
            "present_days": present_count,
            "attendance_rate": round(attendance_rate, 2)
        }
    }), 200

@attendance_bp.route('/attendance/sessions/<int:session_id>', methods=['PUT'])
@jwt_required()
def update_attendance_session(session_id):
    """Update an attendance session and its records"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    session = AttendanceSession.query.get_or_404(session_id)
    
    # Only the original recorder, headteacher, or admin can update
    if current_user.id != session.recorded_by and current_user.role not in ['headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    # Validate records if provided
    if 'records' in data:
        records_errors = validate_attendance_records_data(data['records'], session.class_id)
        if records_errors:
            return jsonify({"error": "Records validation failed", "details": records_errors}), 400
    
    try:
        # Update session metadata if provided
        if 'date' in data:
            session.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'period' in data:
            session.period = data['period']
        if 'is_school_wide' in data:
            session.is_school_wide = data['is_school_wide']
        
        # Update records if provided
        if 'records' in data:
            # First delete existing records
            AttendanceRecord.query.filter_by(session_id=session_id).delete()
            
            # Add new records
            for record_data in data['records']:
                new_record = AttendanceRecord(
                    status=record_data['status'],
                    remarks=record_data.get('remarks'),
                    session_id=session_id,
                    student_id=record_data['student_id']
                )
                db.session.add(new_record)
        
        db.session.commit()
        return jsonify({"message": "Attendance session updated successfully"}), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@attendance_bp.route('/attendance/sessions/<int:session_id>', methods=['DELETE'])
@jwt_required()
def delete_attendance_session(session_id):
    """Delete an attendance session and all its records"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    session = AttendanceSession.query.get_or_404(session_id)
    
    # Only the original recorder, headteacher, or admin can delete
    if current_user.id != session.recorded_by and current_user.role not in ['headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    try:
        # Records will be deleted automatically due to cascade='all, delete-orphan'
        db.session.delete(session)
        db.session.commit()
        return jsonify({"message": "Attendance session deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@attendance_bp.route('/attendance/daily-summary', methods=['GET'])
@jwt_required()
def get_daily_attendance_summary():
    """Get daily attendance summary for the school"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only headteachers and admin can view school-wide summary
    if current_user.role not in ['headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    summary_date = request.args.get('date', str(date.today()))
    
    try:
        summary_date = datetime.strptime(summary_date, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({"error": "Invalid date format (YYYY-MM-DD)"}), 400
    
    # Get all sessions for the date
    sessions = AttendanceSession.query.filter_by(date=summary_date).all()
    
    # Initialize summary data
    summary = {
        "date": summary_date.isoformat(),
        "total_sessions": len(sessions),
        "classes": {},
        "school_wide": {
            "total_students": 0,
            "present_count": 0
        }
    }
    
    # Process each session
    for session in sessions:
        if session.is_school_wide:
            # School-wide attendance (e.g., morning assembly)
            records = AttendanceRecord.query.filter_by(session_id=session.id).all()
            summary["school_wide"]["total_students"] += len(records)
            summary["school_wide"]["present_count"] += len([r for r in records if r.status == 'present'])
        else:
            # Class-specific attendance
            class_id = session.class_id
            if class_id not in summary["classes"]:
                class_ = Class.query.get(class_id)
                summary["classes"][class_id] = {
                    "class_name": class_.name,
                    "stream": class_.stream,
                    "total_sessions": 0,
                    "total_students": 0,
                    "present_count": 0
                }
            
            records = AttendanceRecord.query.filter_by(session_id=session.id).all()
            summary["classes"][class_id]["total_sessions"] += 1
            summary["classes"][class_id]["total_students"] += len(records)
            summary["classes"][class_id]["present_count"] += len([r for r in records if r.status == 'present'])
    
    # Calculate percentages
    if summary["school_wide"]["total_students"] > 0:
        summary["school_wide"]["attendance_rate"] = round(
            (summary["school_wide"]["present_count"] / summary["school_wide"]["total_students"]) * 100, 2
        )
    
    for class_id in summary["classes"]:
        class_data = summary["classes"][class_id]
        if class_data["total_students"] > 0:
            class_data["attendance_rate"] = round(
                (class_data["present_count"] / class_data["total_students"]) * 100, 2
            )
    
    return jsonify(summary), 200