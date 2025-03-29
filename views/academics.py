from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Class, Subject, TeacherSubject, User
from sqlalchemy.exc import IntegrityError

academics_bp = Blueprint('academics', __name__)

# ====================== CLASS MANAGEMENT ======================

@academics_bp.route('/classes', methods=['POST'])
@jwt_required()
def create_class():
    """Create a new class/grade level"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only admin and headteachers can create classes
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    required_fields = ['name', 'academic_year']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        new_class = Class(
            name=data['name'],
            stream=data.get('stream'),
            academic_year=data['academic_year'],
            class_teacher_id=data.get('class_teacher_id')
        )
        
        db.session.add(new_class)
        db.session.commit()
        
        return jsonify({
            "message": "Class created successfully",
            "class": {
                "id": new_class.id,
                "name": new_class.name,
                "stream": new_class.stream,
                "academic_year": new_class.academic_year,
                "class_teacher_id": new_class.class_teacher_id
            }
        }), 201
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Class with this name and stream already exists"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@academics_bp.route('/classes', methods=['GET'])
@jwt_required()
def get_all_classes():
    """Get all classes with optional filtering"""
    query = Class.query
    
    # Filter by academic year if provided
    academic_year = request.args.get('academic_year')
    if academic_year:
        query = query.filter_by(academic_year=academic_year)
    
    classes = query.order_by(Class.name, Class.stream).all()
    
    classes_data = []
    for class_ in classes:
        class_data = {
            "id": class_.id,
            "name": class_.name,
            "stream": class_.stream,
            "academic_year": class_.academic_year,
            "student_count": len(class_.students),
            "subject_count": len(class_.subjects),
            "class_teacher": None
        }
        
        if class_.class_teacher:
            class_data["class_teacher"] = {
                "id": class_.class_teacher.id,
                "name": class_.class_teacher.full_name
            }
        
        classes_data.append(class_data)
    
    return jsonify(classes_data), 200

@academics_bp.route('/classes/<int:class_id>', methods=['GET'])
@jwt_required()
def get_class(class_id):
    """Get detailed information about a specific class"""
    class_ = Class.query.get_or_404(class_id)
    
    # Get class teacher details
    class_teacher = None
    if class_.class_teacher:
        class_teacher = {
            "id": class_.class_teacher.id,
            "name": class_.class_teacher.full_name,
            "email": class_.class_teacher.email
        }
    
    # Get all students in the class
    students = []
    for student in class_.students:
        students.append({
            "id": student.id,
            "admission_number": student.admission_number,
            "full_name": student.full_name,
            "gender": student.gender
        })
    
    # Get all subjects taught in this class
    subjects = []
    for teacher_subject in class_.subjects:
        subject = teacher_subject.subject
        teacher = teacher_subject.teacher
        subjects.append({
            "subject_id": subject.id,
            "subject_name": subject.name,
            "subject_code": subject.code,
            "teacher_id": teacher.id,
            "teacher_name": teacher.full_name
        })
    
    return jsonify({
        "class": {
            "id": class_.id,
            "name": class_.name,
            "stream": class_.stream,
            "academic_year": class_.academic_year,
            "class_teacher": class_teacher,
            "student_count": len(students),
            "subject_count": len(subjects)
        },
        "students": students,
        "subjects": subjects
    }), 200

@academics_bp.route('/classes/<int:class_id>', methods=['PUT'])
@jwt_required()
def update_class(class_id):
    """Update class information"""
    current_user = User.query.get(get_jwt_identity())
    class_ = Class.query.get_or_404(class_id)
    
    # Only admin and headteachers can update classes
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    try:
        if 'name' in data:
            class_.name = data['name']
        if 'stream' in data:
            class_.stream = data['stream']
        if 'academic_year' in data:
            class_.academic_year = data['academic_year']
        if 'class_teacher_id' in data:
            # Verify the new class teacher is a teacher
            new_teacher = User.query.get(data['class_teacher_id'])
            if not new_teacher or new_teacher.role != 'teacher':
                return jsonify({"error": "Invalid class teacher"}), 400
            class_.class_teacher_id = data['class_teacher_id']
        
        db.session.commit()
        
        return jsonify({
            "message": "Class updated successfully",
            "class": {
                "id": class_.id,
                "name": class_.name,
                "stream": class_.stream,
                "academic_year": class_.academic_year,
                "class_teacher_id": class_.class_teacher_id
            }
        }), 200
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Class with this name and stream already exists"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@academics_bp.route('/classes/<int:class_id>', methods=['DELETE'])
@jwt_required()
def delete_class(class_id):
    """Delete a class (only if empty)"""
    current_user = User.query.get(get_jwt_identity())
    class_ = Class.query.get_or_404(class_id)
    
    # Only admin can delete classes
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    # Check if class has students or subjects assigned
    if class_.students:
        return jsonify({"error": "Cannot delete class with students"}), 400
    if class_.subjects:
        return jsonify({"error": "Cannot delete class with assigned subjects"}), 400
    
    try:
        db.session.delete(class_)
        db.session.commit()
        return jsonify({"message": "Class deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ====================== SUBJECT MANAGEMENT ======================

@academics_bp.route('/subjects', methods=['POST'])
@jwt_required()
def create_subject():
    """Create a new subject"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only admin and headteachers can create subjects
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    required_fields = ['name', 'code']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    try:
        new_subject = Subject(
            name=data['name'],
            code=data['code'],
            is_core=data.get('is_core', False)
        )
        
        db.session.add(new_subject)
        db.session.commit()
        
        return jsonify({
            "message": "Subject created successfully",
            "subject": {
                "id": new_subject.id,
                "name": new_subject.name,
                "code": new_subject.code,
                "is_core": new_subject.is_core
            }
        }), 201
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Subject with this name or code already exists"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@academics_bp.route('/subjects', methods=['GET'])
@jwt_required()
def get_all_subjects():
    """Get all subjects"""
    subjects = Subject.query.order_by(Subject.name).all()
    
    subjects_data = []
    for subject in subjects:
        subjects_data.append({
            "id": subject.id,
            "name": subject.name,
            "code": subject.code,
            "is_core": subject.is_core,
            "class_count": len(subject.taught_in_classes)
        })
    
    return jsonify(subjects_data), 200

@academics_bp.route('/subjects/<int:subject_id>', methods=['GET'])
@jwt_required()
def get_subject(subject_id):
    """Get detailed information about a subject"""
    subject = Subject.query.get_or_404(subject_id)
    
    # Get all classes where this subject is taught
    classes = []
    for teacher_subject in subject.taught_in_classes:
        class_ = teacher_subject.class_
        teacher = teacher_subject.teacher
        classes.append({
            "class_id": class_.id,
            "class_name": class_.name,
            "stream": class_.stream,
            "teacher_id": teacher.id,
            "teacher_name": teacher.full_name
        })
    
    return jsonify({
        "subject": {
            "id": subject.id,
            "name": subject.name,
            "code": subject.code,
            "is_core": subject.is_core
        },
        "classes": classes
    }), 200

@academics_bp.route('/subjects/<int:subject_id>', methods=['PUT'])
@jwt_required()
def update_subject(subject_id):
    """Update subject information"""
    current_user = User.query.get(get_jwt_identity())
    subject = Subject.query.get_or_404(subject_id)
    
    # Only admin and headteachers can update subjects
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    try:
        if 'name' in data:
            subject.name = data['name']
        if 'code' in data:
            subject.code = data['code']
        if 'is_core' in data:
            subject.is_core = data['is_core']
        
        db.session.commit()
        
        return jsonify({
            "message": "Subject updated successfully",
            "subject": {
                "id": subject.id,
                "name": subject.name,
                "code": subject.code,
                "is_core": subject.is_core
            }
        }), 200
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Subject with this name or code already exists"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@academics_bp.route('/subjects/<int:subject_id>', methods=['DELETE'])
@jwt_required()
def delete_subject(subject_id):
    """Delete a subject (only if not assigned to any classes)"""
    current_user = User.query.get(get_jwt_identity())
    subject = Subject.query.get_or_404(subject_id)
    
    # Only admin can delete subjects
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    # Check if subject is taught in any classes
    if subject.taught_in_classes:
        return jsonify({"error": "Cannot delete subject assigned to classes"}), 400
    
    try:
        db.session.delete(subject)
        db.session.commit()
        return jsonify({"message": "Subject deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ====================== TEACHER SUBJECT ASSIGNMENT ======================

@academics_bp.route('/teacher-subjects', methods=['POST'])
@jwt_required()
def assign_teacher_to_subject():
    """Assign a teacher to teach a subject in a specific class"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only admin and headteachers can make assignments
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    required_fields = ['teacher_id', 'subject_id', 'class_id']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    # Verify teacher exists and is a teacher
    teacher = User.query.get(data['teacher_id'])
    if not teacher or teacher.role != 'teacher':
        return jsonify({"error": "Invalid teacher"}), 400
    
    # Verify subject exists
    if not Subject.query.get(data['subject_id']):
        return jsonify({"error": "Subject not found"}), 404
    
    # Verify class exists
    if not Class.query.get(data['class_id']):
        return jsonify({"error": "Class not found"}), 404
    
    try:
        new_assignment = TeacherSubject(
            teacher_id=data['teacher_id'],
            subject_id=data['subject_id'],
            class_id=data['class_id']
        )
        
        db.session.add(new_assignment)
        db.session.commit()
        
        return jsonify({
            "message": "Teacher assigned to subject successfully",
            "assignment": {
                "id": new_assignment.id,
                "teacher_id": new_assignment.teacher_id,
                "teacher_name": teacher.full_name,
                "subject_id": new_assignment.subject_id,
                "subject_name": Subject.query.get(new_assignment.subject_id).name,
                "class_id": new_assignment.class_id,
                "class_name": Class.query.get(new_assignment.class_id).name
            }
        }), 201
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "This teacher is already assigned to this subject in this class"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@academics_bp.route('/teacher-subjects/<int:assignment_id>', methods=['DELETE'])
@jwt_required()
def remove_teacher_subject_assignment(assignment_id):
    """Remove a teacher's subject assignment"""
    current_user = User.query.get(get_jwt_identity())
    assignment = TeacherSubject.query.get_or_404(assignment_id)
    
    # Only admin and headteachers can remove assignments
    if current_user.role not in ['admin', 'headteacher']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    try:
        db.session.delete(assignment)
        db.session.commit()
        return jsonify({"message": "Teacher assignment removed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@academics_bp.route('/teachers/<int:teacher_id>/subjects', methods=['GET'])
@jwt_required()
def get_teacher_assignments(teacher_id):
    """Get all subject assignments for a teacher"""
    teacher = User.query.get_or_404(teacher_id)
    if teacher.role != 'teacher':
        return jsonify({"error": "User is not a teacher"}), 400
    
    assignments = TeacherSubject.query.filter_by(teacher_id=teacher_id).all()
    
    assignments_data = []
    for assignment in assignments:
        subject = assignment.subject
        class_ = assignment.class_
        assignments_data.append({
            "assignment_id": assignment.id,
            "subject_id": subject.id,
            "subject_name": subject.name,
            "subject_code": subject.code,
            "class_id": class_.id,
            "class_name": class_.name,
            "stream": class_.stream,
            "academic_year": class_.academic_year
        })
    
    return jsonify({
        "teacher": {
            "id": teacher.id,
            "name": teacher.full_name
        },
        "assignments": assignments_data
    }), 200