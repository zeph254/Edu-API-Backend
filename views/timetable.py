from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Timetable, Class, Subject, User
from datetime import datetime
from sqlalchemy.exc import IntegrityError

timetable_bp = Blueprint('timetable', __name__)

# Helper function to validate timetable data
def validate_timetable_data(data, is_update=False):
    errors = {}
    
    required_fields = ['day', 'period', 'subject_id', 'class_id', 'teacher_id']
    if not is_update:
        for field in required_fields:
            if field not in data:
                errors[field] = f"{field.replace('_', ' ').title()} is required"
    
    if 'day' in data and data['day'].capitalize() not in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
        errors['day'] = "Invalid day of week"
    
    if 'period' in data and not isinstance(data['period'], int) or data['period'] < 1 or data['period'] > 8:
        errors['period'] = "Period must be an integer between 1 and 8"
    
    if 'subject_id' in data and not Subject.query.get(data['subject_id']):
        errors['subject_id'] = "Subject not found"
    
    if 'class_id' in data and not Class.query.get(data['class_id']):
        errors['class_id'] = "Class not found"
    
    if 'teacher_id' in data and not User.query.get(data['teacher_id']):
        errors['teacher_id'] = "Teacher not found"
    
    return errors if errors else None

@timetable_bp.route('/timetable', methods=['POST'])
@jwt_required()
def create_timetable_entry():
    """Create a new timetable entry"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only admin and headteachers can create timetable entries
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    validation_errors = validate_timetable_data(data)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
    
    try:
        new_entry = Timetable(
            day=data['day'].capitalize(),
            period=data['period'],
            room=data.get('room'),
            subject_id=data['subject_id'],
            class_id=data['class_id'],
            teacher_id=data['teacher_id']
        )
        
        db.session.add(new_entry)
        db.session.commit()
        
        return jsonify({
            "message": "Timetable entry created successfully",
            "entry": {
                "id": new_entry.id,
                "day": new_entry.day,
                "period": new_entry.period,
                "room": new_entry.room,
                "subject": Subject.query.get(new_entry.subject_id).name,
                "class": Class.query.get(new_entry.class_id).name,
                "teacher": User.query.get(new_entry.teacher_id).full_name
            }
        }), 201
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Timetable entry conflicts with existing entry"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@timetable_bp.route('/timetable/<int:entry_id>', methods=['GET'])
@jwt_required()
def get_timetable_entry(entry_id):
    """Get a specific timetable entry"""
    entry = Timetable.query.get_or_404(entry_id)
    
    return jsonify({
        "id": entry.id,
        "day": entry.day,
        "period": entry.period,
        "room": entry.room,
        "subject": {
            "id": entry.subject_id,
            "name": Subject.query.get(entry.subject_id).name
        },
        "class": {
            "id": entry.class_id,
            "name": Class.query.get(entry.class_id).name,
            "stream": Class.query.get(entry.class_id).stream
        },
        "teacher": {
            "id": entry.teacher_id,
            "name": User.query.get(entry.teacher_id).full_name
        }
    }), 200

@timetable_bp.route('/timetable/class/<int:class_id>', methods=['GET'])
@jwt_required()
def get_class_timetable(class_id):
    """Get timetable for a specific class"""
    class_ = Class.query.get_or_404(class_id)
    entries = Timetable.query.filter_by(class_id=class_id).order_by(Timetable.day, Timetable.period).all()
    
    timetable = {}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Initialize empty timetable structure
    for day in days:
        timetable[day] = {period: None for period in range(1, 9)}  # Assuming 8 periods per day
    
    # Fill in the timetable entries
    for entry in entries:
        if entry.day in timetable and entry.period in timetable[entry.day]:
            timetable[entry.day][entry.period] = {
                "id": entry.id,
                "subject": Subject.query.get(entry.subject_id).name,
                "teacher": User.query.get(entry.teacher_id).full_name,
                "room": entry.room
            }
    
    return jsonify({
        "class": {
            "id": class_.id,
            "name": class_.name,
            "stream": class_.stream,
            "academic_year": class_.academic_year
        },
        "timetable": timetable
    }), 200

@timetable_bp.route('/timetable/teacher/<int:teacher_id>', methods=['GET'])
@jwt_required()
def get_teacher_timetable(teacher_id):
    """Get timetable for a specific teacher"""
    teacher = User.query.get_or_404(teacher_id)
    if teacher.role != 'teacher':
        return jsonify({"error": "User is not a teacher"}), 400
    
    entries = Timetable.query.filter_by(teacher_id=teacher_id).order_by(Timetable.day, Timetable.period).all()
    
    timetable = {}
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    # Initialize empty timetable structure
    for day in days:
        timetable[day] = {period: None for period in range(1, 9)}  # Assuming 8 periods per day
    
    # Fill in the timetable entries
    for entry in entries:
        if entry.day in timetable and entry.period in timetable[entry.day]:
            timetable[entry.day][entry.period] = {
                "id": entry.id,
                "subject": Subject.query.get(entry.subject_id).name,
                "class": Class.query.get(entry.class_id).name,
                "stream": Class.query.get(entry.class_id).stream,
                "room": entry.room
            }
    
    return jsonify({
        "teacher": {
            "id": teacher.id,
            "name": teacher.full_name
        },
        "timetable": timetable
    }), 200

@timetable_bp.route('/timetable/<int:entry_id>', methods=['PUT'])
@jwt_required()
def update_timetable_entry(entry_id):
    """Update a timetable entry"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only admin and headteachers can update timetable entries
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    entry = Timetable.query.get_or_404(entry_id)
    data = request.get_json()
    
    validation_errors = validate_timetable_data(data, is_update=True)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
    
    try:
        if 'day' in data:
            entry.day = data['day'].capitalize()
        if 'period' in data:
            entry.period = data['period']
        if 'room' in data:
            entry.room = data['room']
        if 'subject_id' in data:
            entry.subject_id = data['subject_id']
        if 'class_id' in data:
            entry.class_id = data['class_id']
        if 'teacher_id' in data:
            entry.teacher_id = data['teacher_id']
        
        db.session.commit()
        
        return jsonify({
            "message": "Timetable entry updated successfully",
            "entry": {
                "id": entry.id,
                "day": entry.day,
                "period": entry.period,
                "room": entry.room,
                "subject": Subject.query.get(entry.subject_id).name,
                "class": Class.query.get(entry.class_id).name,
                "teacher": User.query.get(entry.teacher_id).full_name
            }
        }), 200
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Timetable entry conflicts with existing entry"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@timetable_bp.route('/timetable/<int:entry_id>', methods=['DELETE'])
@jwt_required()
def delete_timetable_entry(entry_id):
    """Delete a timetable entry"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only admin and headteachers can delete timetable entries
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    entry = Timetable.query.get_or_404(entry_id)
    
    try:
        db.session.delete(entry)
        db.session.commit()
        return jsonify({"message": "Timetable entry deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@timetable_bp.route('/timetable/check-conflicts', methods=['POST'])
@jwt_required()
def check_timetable_conflicts():
    """Check for timetable conflicts"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only admin and headteachers can check conflicts
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    validation_errors = validate_timetable_data(data)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
    
    # Check for conflicts
    conflicts = []
    
    # Check if teacher is already scheduled at this time
    teacher_conflict = Timetable.query.filter_by(
        day=data['day'].capitalize(),
        period=data['period'],
        teacher_id=data['teacher_id']
    ).first()
    
    if teacher_conflict:
        conflicts.append({
            "type": "teacher",
            "message": f"Teacher is already teaching {teacher_conflict.subject.name} to {teacher_conflict.class_.name} at this time",
            "conflicting_entry": {
                "id": teacher_conflict.id,
                "subject": teacher_conflict.subject.name,
                "class": teacher_conflict.class_.name
            }
        })
    
    # Check if class is already scheduled at this time
    class_conflict = Timetable.query.filter_by(
        day=data['day'].capitalize(),
        period=data['period'],
        class_id=data['class_id']
    ).first()
    
    if class_conflict:
        conflicts.append({
            "type": "class",
            "message": f"Class is already having {class_conflict.subject.name} with {class_conflict.teacher.full_name} at this time",
            "conflicting_entry": {
                "id": class_conflict.id,
                "subject": class_conflict.subject.name,
                "teacher": class_conflict.teacher.full_name
            }
        })
    
    # Check if room is already in use at this time (if room is provided)
    if 'room' in data and data['room']:
        room_conflict = Timetable.query.filter_by(
            day=data['day'].capitalize(),
            period=data['period'],
            room=data['room']
        ).first()
        
        if room_conflict:
            conflicts.append({
                "type": "room",
                "message": f"Room is already occupied by {room_conflict.class_.name} for {room_conflict.subject.name} at this time",
                "conflicting_entry": {
                    "id": room_conflict.id,
                    "class": room_conflict.class_.name,
                    "subject": room_conflict.subject.name
                }
            })
    
    return jsonify({
        "has_conflicts": len(conflicts) > 0,
        "conflicts": conflicts
    }), 200