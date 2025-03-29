from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from models import db, StudentPerformance, Student, Assessment, User,Class
from sqlalchemy.exc import IntegrityError

performance_bp = Blueprint('performance', __name__)

# Helper functions
def validate_performance_data(data, is_update=False):
    errors = {}
    
    required_fields = ['student_id', 'assessment_id', 'recorded_by']
    if not is_update:
        for field in required_fields:
            if field not in data:
                errors[field] = f"{field.replace('_', ' ').title()} is required"
    
    if 'student_id' in data and not Student.query.get(data['student_id']):
        errors['student_id'] = "Student not found"
    
    if 'assessment_id' in data and not Assessment.query.get(data['assessment_id']):
        errors['assessment_id'] = "Assessment not found"
    
    if 'recorded_by' in data and not User.query.get(data['recorded_by']):
        errors['recorded_by'] = "User not found"
    
    if 'score' in data and data['score'] is not None:
        try:
            score = float(data['score'])
            assessment = Assessment.query.get(data.get('assessment_id', 0))
            if assessment and score > assessment.max_score:
                errors['score'] = f"Score cannot exceed maximum ({assessment.max_score})"
        except ValueError:
            errors['score'] = "Score must be a number"
    
    return errors if errors else None

@performance_bp.route('/performances', methods=['POST'])
@jwt_required()
def create_performance():
    """Record student performance for an assessment"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Only teachers, headteachers, and admin can record performance
    if current_user.role not in ['teacher', 'headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    validation_errors = validate_performance_data(data)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
    
    # Verify the current user is authorized to record this performance
    if str(current_user.id) != str(data['recorded_by']):
        return jsonify({"error": "You can only record performance as yourself"}), 403
    
    try:
        new_performance = StudentPerformance(
            student_id=data['student_id'],
            assessment_id=data['assessment_id'],
            recorded_by=data['recorded_by'],
            score=data.get('score'),
            competency_level=data.get('competency_level'),
            strand=data.get('strand'),
            sub_strand=data.get('sub_strand'),
            comments=data.get('comments')
        )
        
        db.session.add(new_performance)
        db.session.commit()
        
        # Get related data for response
        student = Student.query.get(data['student_id'])
        assessment = Assessment.query.get(data['assessment_id'])
        
        return jsonify({
            "message": "Performance recorded successfully",
            "performance": {
                "id": new_performance.id,
                "student": {
                    "id": student.id,
                    "name": student.full_name,
                    "admission_number": student.admission_number
                },
                "assessment": {
                    "id": assessment.id,
                    "name": assessment.name,
                    "type": assessment.assessment_type,
                    "max_score": assessment.max_score,
                    "is_cbc": assessment.is_cbc
                },
                "score": new_performance.score,
                "competency_level": new_performance.competency_level,
                "strand": new_performance.strand,
                "sub_strand": new_performance.sub_strand,
                "comments": new_performance.comments,
                "recorded_by": current_user.full_name,
                "recorded_at": datetime.utcnow().isoformat()
            }
        }), 201
    
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Performance record for this student and assessment already exists"}), 409
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@performance_bp.route('/performances/<int:performance_id>', methods=['GET'])
@jwt_required()
def get_performance(performance_id):
    """Get a specific performance record"""
    performance = StudentPerformance.query.get_or_404(performance_id)
    
    student = performance.student
    assessment = performance.assessment
    recorded_by = performance.recorded_by_user
    
    return jsonify({
        "id": performance.id,
        "student": {
            "id": student.id,
            "name": student.full_name,
            "admission_number": student.admission_number,
            "class": {
                "id": student.class_.id,
                "name": student.class_.name,
                "stream": student.class_.stream
            }
        },
        "assessment": {
            "id": assessment.id,
            "name": assessment.name,
            "type": assessment.assessment_type,
            "date": assessment.date.isoformat() if assessment.date else None,
            "max_score": assessment.max_score,
            "is_cbc": assessment.is_cbc,
            "subject": {
                "id": assessment.subject.id,
                "name": assessment.subject.name
            }
        },
        "score": performance.score,
        "competency_level": performance.competency_level,
        "strand": performance.strand,
        "sub_strand": performance.sub_strand,
        "comments": performance.comments,
        "recorded_by": {
            "id": recorded_by.id,
            "name": recorded_by.full_name,
            "role": recorded_by.role
        },
        "recorded_at": performance.created_at.isoformat() if performance.created_at else None
    }), 200

@performance_bp.route('/students/<int:student_id>/performances', methods=['GET'])
@jwt_required()
def get_student_performances(student_id):
    """Get all performance records for a student"""
    student = Student.query.get_or_404(student_id)
    subject_id = request.args.get('subject_id')
    assessment_type = request.args.get('type')
    is_cbc = request.args.get('is_cbc')
    
    query = StudentPerformance.query.filter_by(student_id=student_id)
    
    # Apply filters if provided
    if subject_id:
        query = query.join(Assessment).filter(Assessment.subject_id == subject_id)
    
    if assessment_type:
        query = query.join(Assessment).filter(Assessment.assessment_type == assessment_type)
    
    if is_cbc is not None:
        is_cbc_bool = is_cbc.lower() == 'true'
        query = query.join(Assessment).filter(Assessment.is_cbc == is_cbc_bool)
    
    performances = query.order_by(Assessment.date.desc()).all()
    
    performances_data = []
    for performance in performances:
        assessment = performance.assessment
        performances_data.append({
            "id": performance.id,
            "assessment": {
                "id": assessment.id,
                "name": assessment.name,
                "type": assessment.assessment_type,
                "date": assessment.date.isoformat() if assessment.date else None,
                "max_score": assessment.max_score,
                "is_cbc": assessment.is_cbc,
                "subject": {
                    "id": assessment.subject.id,
                    "name": assessment.subject.name
                }
            },
            "score": performance.score,
            "competency_level": performance.competency_level,
            "strand": performance.strand,
            "sub_strand": performance.sub_strand,
            "comments": performance.comments,
            "recorded_at": performance.created_at.isoformat() if performance.created_at else None
        })
    
    return jsonify({
        "student": {
            "id": student.id,
            "name": student.full_name,
            "admission_number": student.admission_number,
            "class": {
                "id": student.class_.id,
                "name": student.class_.name,
                "stream": student.class_.stream
            }
        },
        "performances": performances_data,
        "count": len(performances_data)
    }), 200

@performance_bp.route('/assessments/<int:assessment_id>/performances', methods=['GET'])
@jwt_required()
def get_assessment_performances(assessment_id):
    """Get all performance records for an assessment"""
    assessment = Assessment.query.get_or_404(assessment_id)
    
    performances = StudentPerformance.query.filter_by(assessment_id=assessment_id).all()
    
    performances_data = []
    for performance in performances:
        student = performance.student
        performances_data.append({
            "id": performance.id,
            "student": {
                "id": student.id,
                "name": student.full_name,
                "admission_number": student.admission_number
            },
            "score": performance.score,
            "competency_level": performance.competency_level,
            "strand": performance.strand,
            "sub_strand": performance.sub_strand,
            "comments": performance.comments,
            "recorded_at": performance.created_at.isoformat() if performance.created_at else None
        })
    
    # Calculate statistics
    scores = [p.score for p in performances if p.score is not None]
    stats = {}
    if scores:
        stats = {
            "average": round(sum(scores) / len(scores), 2),
            "highest": max(scores),
            "lowest": min(scores),
            "count": len(scores)
        }
    
    return jsonify({
        "assessment": {
            "id": assessment.id,
            "name": assessment.name,
            "type": assessment.assessment_type,
            "date": assessment.date.isoformat() if assessment.date else None,
            "max_score": assessment.max_score,
            "is_cbc": assessment.is_cbc,
            "subject": {
                "id": assessment.subject.id,
                "name": assessment.subject.name
            },
            "class": {
                "id": assessment.class_.id,
                "name": assessment.class_.name,
                "stream": assessment.class_.stream
            }
        },
        "performances": performances_data,
        "statistics": stats
    }), 200

@performance_bp.route('/performances/<int:performance_id>', methods=['PUT'])
@jwt_required()
def update_performance(performance_id):
    """Update a performance record"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    performance = StudentPerformance.query.get_or_404(performance_id)
    
    # Only the original recorder, headteacher, or admin can update
    if (current_user.id != performance.recorded_by and 
        current_user.role not in ['headteacher', 'admin']):
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    validation_errors = validate_performance_data(data, is_update=True)
    if validation_errors:
        return jsonify({"error": "Validation failed", "details": validation_errors}), 400
    
    try:
        if 'score' in data:
            performance.score = data['score']
        if 'competency_level' in data:
            performance.competency_level = data['competency_level']
        if 'strand' in data:
            performance.strand = data['strand']
        if 'sub_strand' in data:
            performance.sub_strand = data['sub_strand']
        if 'comments' in data:
            performance.comments = data['comments']
        
        db.session.commit()
        
        return jsonify({
            "message": "Performance updated successfully",
            "performance": {
                "id": performance.id,
                "student_id": performance.student_id,
                "assessment_id": performance.assessment_id,
                "score": performance.score,
                "competency_level": performance.competency_level,
                "strand": performance.strand,
                "sub_strand": performance.sub_strand,
                "comments": performance.comments
            }
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@performance_bp.route('/performances/<int:performance_id>', methods=['DELETE'])
@jwt_required()
def delete_performance(performance_id):
    """Delete a performance record"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    performance = StudentPerformance.query.get_or_404(performance_id)
    
    # Only the original recorder, headteacher, or admin can delete
    if (current_user.id != performance.recorded_by and 
        current_user.role not in ['headteacher', 'admin']):
        return jsonify({"error": "Unauthorized access"}), 403
    
    try:
        db.session.delete(performance)
        db.session.commit()
        return jsonify({"message": "Performance record deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@performance_bp.route('/classes/<int:class_id>/performance-summary', methods=['GET'])
@jwt_required()
def get_class_performance_summary(class_id):
    """Get performance summary for a class"""
    class_ = Class.query.get_or_404(class_id)
    subject_id = request.args.get('subject_id')
    
    query = Assessment.query.filter_by(class_id=class_id)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    
    assessments = query.all()
    
    summary = []
    for assessment in assessments:
        performances = StudentPerformance.query.filter_by(assessment_id=assessment.id).all()
        scores = [p.score for p in performances if p.score is not None]
        
        assessment_data = {
            "assessment_id": assessment.id,
            "assessment_name": assessment.name,
            "assessment_type": assessment.assessment_type,
            "date": assessment.date.isoformat() if assessment.date else None,
            "max_score": assessment.max_score,
            "is_cbc": assessment.is_cbc,
            "subject": {
                "id": assessment.subject.id,
                "name": assessment.subject.name
            },
            "performance_count": len(performances),
            "statistics": {}
        }
        
        if scores:
            assessment_data["statistics"] = {
                "average": round(sum(scores) / len(scores), 2),
                "highest": max(scores),
                "lowest": min(scores),
                "count": len(scores)
            }
        
        summary.append(assessment_data)
    
    return jsonify({
        "class": {
            "id": class_.id,
            "name": class_.name,
            "stream": class_.stream
        },
        "assessments": summary
    }), 200