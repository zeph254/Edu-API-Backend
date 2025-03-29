from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User, Class, Subject, Student,TeacherSubject
from werkzeug.security import generate_password_hash
from sqlalchemy.exc import IntegrityError

admin_bp = Blueprint('admin', __name__)

# ====================== USER MANAGEMENT ======================

@admin_bp.route('/users', methods=['POST'])
@jwt_required()
def create_user():
    """Create a new user (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only admin can create users
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    required_fields = ['username', 'email', 'password', 'role', 'full_name']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400
    
    if User.query.filter((User.username == data["username"]) | (User.email == data["email"])).first():
        return jsonify({"error": "Username or email already exists"}), 409
    
    try:
        new_user = User(
            username=data["username"],
            email=data["email"],
            role=data["role"],
            full_name=data["full_name"],
            phone=data.get("phone"),
            is_active=data.get("is_active", True)
        )
        new_user.set_password(data["password"])
        
        db.session.add(new_user)
        db.session.commit()

        return jsonify({
            "message": "User created successfully",
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "email": new_user.email,
                "role": new_user.role,
                "full_name": new_user.full_name,
                "is_active": new_user.is_active
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_users():
    """Get all users (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    users = User.query.order_by(User.role, User.full_name).all()
    
    users_data = []
    for user in users:
        users_data.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "full_name": user.full_name,
            "phone": user.phone,
            "is_active": user.is_active,
            "last_login": user.last_login.isoformat() if user.last_login else None
        })
    
    return jsonify(users_data), 200

@admin_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Get user details (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    user = User.query.get_or_404(user_id)
    
    # Get classes taught if teacher
    classes_taught = []
    if user.role == 'teacher':
        for ts in user.taught_subjects:
            class_ = ts.class_
            subject = ts.subject
            classes_taught.append({
                "class_id": class_.id,
                "class_name": class_.name,
                "stream": class_.stream,
                "subject_id": subject.id,
                "subject_name": subject.name
            })
    
    # Get class teacher info if applicable
    class_teacher_info = None
    if user.class_teacher:
        class_ = user.class_teacher[0]  # Assuming one class per teacher
        class_teacher_info = {
            "class_id": class_.id,
            "class_name": class_.name,
            "stream": class_.stream,
            "academic_year": class_.academic_year
        }
    
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "phone": user.phone,
        "is_active": user.is_active,
        "last_login": user.last_login.isoformat() if user.last_login else None,
        "classes_taught": classes_taught,
        "class_teacher_info": class_teacher_info
    }), 200

@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Update user information (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    try:
        if 'username' in data:
            if User.query.filter(User.username == data['username'], User.id != user_id).first():
                return jsonify({"error": "Username already in use"}), 409
            user.username = data['username']
        
        if 'email' in data:
            if User.query.filter(User.email == data['email'], User.id != user_id).first():
                return jsonify({"error": "Email already in use"}), 409
            user.email = data['email']
        
        if 'full_name' in data:
            user.full_name = data['full_name']
        
        if 'phone' in data:
            user.phone = data['phone']
        
        if 'role' in data:
            user.role = data['role']
        
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        if 'password' in data:
            user.set_password(data['password'])
        
        db.session.commit()
        
        return jsonify({
            "message": "User updated successfully",
            "user": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "full_name": user.full_name,
                "is_active": user.is_active
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Delete a user (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    if current_user.id == user_id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    
    user = User.query.get_or_404(user_id)
    
    # Check if user is a class teacher
    if user.class_teacher:
        return jsonify({"error": "Cannot delete user who is a class teacher"}), 400
    
    # Check if user has taught subjects
    if user.taught_subjects:
        return jsonify({"error": "Cannot delete user who is assigned to teach subjects"}), 400
    
    try:
        db.session.delete(user)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ====================== SYSTEM CONFIGURATION ======================

@admin_bp.route('/config/academic-year', methods=['POST'])
@jwt_required()
def set_academic_year():
    """Set academic year for all classes (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    if 'academic_year' not in data:
        return jsonify({"error": "Missing academic_year"}), 400
    
    try:
        # Update all classes
        Class.query.update({'academic_year': data['academic_year']})
        db.session.commit()
        
        return jsonify({
            "message": "Academic year updated successfully",
            "academic_year": data['academic_year']
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ====================== BULK OPERATIONS ======================

@admin_bp.route('/bulk/students', methods=['POST'])
@jwt_required()
def bulk_create_students():
    """Bulk create students (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    if not isinstance(data, list):
        return jsonify({"error": "Expected an array of student data"}), 400
    
    required_fields = ['admission_number', 'full_name', 'class_id']
    errors = []
    students = []
    
    for i, student_data in enumerate(data):
        if not all(field in student_data for field in required_fields):
            errors.append(f"Student {i}: Missing required fields")
            continue
        
        if Student.query.filter_by(admission_number=student_data['admission_number']).first():
            errors.append(f"Student {i}: Admission number already exists")
            continue
        
        if not Class.query.get(student_data['class_id']):
            errors.append(f"Student {i}: Class not found")
            continue
        
        students.append(Student(
            admission_number=student_data['admission_number'],
            full_name=student_data['full_name'],
            class_id=student_data['class_id'],
            date_of_birth=student_data.get('date_of_birth'),
            gender=student_data.get('gender'),
            parent_name=student_data.get('parent_name'),
            parent_phone=student_data.get('parent_phone'),
            address=student_data.get('address')
        ))
    
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    
    try:
        db.session.bulk_save_objects(students)
        db.session.commit()
        
        return jsonify({
            "message": f"{len(students)} students created successfully",
            "count": len(students)
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@admin_bp.route('/bulk/teacher-assignments', methods=['POST'])
@jwt_required()
def bulk_assign_teachers():
    """Bulk assign teachers to subjects in classes (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    if not isinstance(data, list):
        return jsonify({"error": "Expected an array of assignment data"}), 400
    
    required_fields = ['teacher_id', 'subject_id', 'class_id']
    errors = []
    assignments = []
    
    for i, assignment_data in enumerate(data):
        if not all(field in assignment_data for field in required_fields):
            errors.append(f"Assignment {i}: Missing required fields")
            continue
        
        teacher = User.query.get(assignment_data['teacher_id'])
        if not teacher or teacher.role != 'teacher':
            errors.append(f"Assignment {i}: Invalid teacher")
            continue
        
        if not Subject.query.get(assignment_data['subject_id']):
            errors.append(f"Assignment {i}: Subject not found")
            continue
        
        if not Class.query.get(assignment_data['class_id']):
            errors.append(f"Assignment {i}: Class not found")
            continue
        
        if TeacherSubject.query.filter_by(
            teacher_id=assignment_data['teacher_id'],
            subject_id=assignment_data['subject_id'],
            class_id=assignment_data['class_id']
        ).first():
            errors.append(f"Assignment {i}: Teacher already assigned to this subject in class")
            continue
        
        assignments.append(TeacherSubject(
            teacher_id=assignment_data['teacher_id'],
            subject_id=assignment_data['subject_id'],
            class_id=assignment_data['class_id']
        ))
    
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    
    try:
        db.session.bulk_save_objects(assignments)
        db.session.commit()
        
        return jsonify({
            "message": f"{len(assignments)} teacher assignments created successfully",
            "count": len(assignments)
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# ====================== SYSTEM MAINTENANCE ======================

@admin_bp.route('/maintenance/cleanup', methods=['POST'])
@jwt_required()
def system_cleanup():
    """Perform system cleanup (admin only)"""
    current_user = User.query.get(get_jwt_identity())
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    try:
        # Example cleanup operations:
        # 1. Delete empty classes
        # 2. Delete orphaned records
        # 3. Archive old data
        
        # This is just a placeholder - implement actual cleanup logic as needed
        deleted_count = 0
        
        return jsonify({
            "message": "System cleanup completed",
            "deleted_records": deleted_count
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500