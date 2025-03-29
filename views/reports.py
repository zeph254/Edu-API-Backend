from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from models import db, Student, Class, Subject, AttendanceSession, AttendanceRecord, StudentPerformance, Assessment,User
from sqlalchemy import func, and_, or_, case
import csv
from io import StringIO

reports_bp = Blueprint('reports', __name__)

# Helper functions
def generate_report_filename(report_type, format):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{report_type}_report_{timestamp}.{format}"

# ====================== ATTENDANCE REPORTS ======================

@reports_bp.route('/reports/attendance/class-summary', methods=['GET'])
@jwt_required()
def get_class_attendance_summary():
    """Generate attendance summary report for classes"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only teachers, headteachers, and admin can access attendance reports
    if current_user.role not in ['teacher', 'headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    class_id = request.args.get('class_id')
    format = request.args.get('format', 'json')  # json or csv
    
    try:
        # Parse date filters
        date_filters = []
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_filters.append(AttendanceSession.date >= date_from)
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            date_filters.append(AttendanceSession.date <= date_to)
        
        # Base query
        query = db.session.query(
            Class.id.label('class_id'),
            Class.name.label('class_name'),
            Class.stream,
            func.count(AttendanceSession.id).label('total_sessions'),
            func.count(AttendanceRecord.id).label('total_records'),
            func.sum(case([(AttendanceRecord.status == 'present', 1)], else_=0)).label('present_count')
        ).join(AttendanceSession, Class.id == AttendanceSession.class_id
        ).join(AttendanceRecord, AttendanceSession.id == AttendanceRecord.session_id
        ).group_by(Class.id, Class.name, Class.stream)
        
        # Apply filters
        if date_filters:
            query = query.filter(and_(*date_filters))
        if class_id:
            query = query.filter(Class.id == class_id)
        
        # For teachers, only show their own classes
        if current_user.role == 'teacher':
            query = query.filter(or_(
                Class.class_teacher_id == current_user.id,
                Class.id.in_([ts.class_id for ts in current_user.taught_subjects])
            ))
        
        results = query.all()
        
        # Prepare report data
        report_data = []
        for result in results:
            attendance_rate = (result.present_count / result.total_records * 100) if result.total_records > 0 else 0
            report_data.append({
                "class_id": result.class_id,
                "class_name": result.class_name,
                "stream": result.stream,
                "total_sessions": result.total_sessions,
                "total_records": result.total_records,
                "present_count": result.present_count,
                "attendance_rate": round(attendance_rate, 2)
            })
        
        # Handle different output formats
        if format == 'csv':
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['Class ID', 'Class Name', 'Stream', 'Total Sessions', 'Total Records', 'Present Count', 'Attendance Rate (%)'])
            for row in report_data:
                cw.writerow([
                    row['class_id'],
                    row['class_name'],
                    row['stream'],
                    row['total_sessions'],
                    row['total_records'],
                    row['present_count'],
                    row['attendance_rate']
                ])
            output = si.getvalue()
            filename = generate_report_filename('class_attendance_summary', 'csv')
            return output, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename={filename}'
            }
        else:
            return jsonify({
                "report_type": "class_attendance_summary",
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "data": report_data
            }), 200
    
    except ValueError as e:
        return jsonify({"error": "Invalid date format (YYYY-MM-DD)"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/reports/attendance/student-details', methods=['GET'])
@jwt_required()
def get_student_attendance_details():
    """Generate detailed attendance report for students"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only teachers, headteachers, and admin can access attendance reports
    if current_user.role not in ['teacher', 'headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    date_from = request.args.get('from')
    date_to = request.args.get('to')
    class_id = request.args.get('class_id')
    student_id = request.args.get('student_id')
    format = request.args.get('format', 'json')  # json or csv
    
    try:
        # Parse date filters
        date_filters = []
        if date_from:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_filters.append(AttendanceSession.date >= date_from)
        if date_to:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            date_filters.append(AttendanceSession.date <= date_to)
        
        # Base query
        query = db.session.query(
            Student.id.label('student_id'),
            Student.full_name,
            Student.admission_number,
            Class.name.label('class_name'),
            Class.stream,
            AttendanceSession.date,
            AttendanceRecord.status,
            AttendanceRecord.remarks
        ).join(Class, Student.class_id == Class.id
        ).join(AttendanceRecord, Student.id == AttendanceRecord.student_id
        ).join(AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
        ).order_by(Student.full_name, AttendanceSession.date)
        
        # Apply filters
        if date_filters:
            query = query.filter(and_(*date_filters))
        if class_id:
            query = query.filter(Class.id == class_id)
        if student_id:
            query = query.filter(Student.id == student_id)
        
        # For teachers, only show their own classes
        if current_user.role == 'teacher':
            query = query.filter(or_(
                Class.class_teacher_id == current_user.id,
                Class.id.in_([ts.class_id for ts in current_user.taught_subjects])
            ))
        
        results = query.all()
        
        # Prepare report data
        report_data = []
        for result in results:
            report_data.append({
                "student_id": result.student_id,
                "student_name": result.full_name,
                "admission_number": result.admission_number,
                "class_name": result.class_name,
                "stream": result.stream,
                "date": result.date.isoformat(),
                "status": result.status,
                "remarks": result.remarks
            })
        
        # Handle different output formats
        if format == 'csv':
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['Student ID', 'Student Name', 'Admission Number', 'Class', 'Stream', 'Date', 'Status', 'Remarks'])
            for row in report_data:
                cw.writerow([
                    row['student_id'],
                    row['student_name'],
                    row['admission_number'],
                    row['class_name'],
                    row['stream'],
                    row['date'],
                    row['status'],
                    row['remarks']
                ])
            output = si.getvalue()
            filename = generate_report_filename('student_attendance_details', 'csv')
            return output, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename={filename}'
            }
        else:
            return jsonify({
                "report_type": "student_attendance_details",
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "data": report_data
            }), 200
    
    except ValueError as e:
        return jsonify({"error": "Invalid date format (YYYY-MM-DD)"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ====================== PERFORMANCE REPORTS ======================

@reports_bp.route('/reports/performance/class-summary', methods=['GET'])
@jwt_required()
def get_class_performance_summary():
    """Generate performance summary report for classes"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only teachers, headteachers, and admin can access performance reports
    if current_user.role not in ['teacher', 'headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    class_id = request.args.get('class_id')
    subject_id = request.args.get('subject_id')
    assessment_type = request.args.get('type')
    is_cbc = request.args.get('is_cbc')
    format = request.args.get('format', 'json')  # json or csv
    
    try:
        # Base query
        query = db.session.query(
            Class.id.label('class_id'),
            Class.name.label('class_name'),
            Class.stream,
            Subject.id.label('subject_id'),
            Subject.name.label('subject_name'),
            Assessment.id.label('assessment_id'),
            Assessment.name.label('assessment_name'),
            Assessment.assessment_type,
            Assessment.date,
            Assessment.max_score,
            func.count(StudentPerformance.id).label('record_count'),
            func.avg(StudentPerformance.score).label('average_score'),
            func.max(StudentPerformance.score).label('highest_score'),
            func.min(StudentPerformance.score).label('lowest_score')
        ).join(Student, Class.id == Student.class_id
        ).join(StudentPerformance, Student.id == StudentPerformance.student_id
        ).join(Assessment, StudentPerformance.assessment_id == Assessment.id
        ).join(Subject, Assessment.subject_id == Subject.id
        ).group_by(
            Class.id, Class.name, Class.stream,
            Subject.id, Subject.name,
            Assessment.id, Assessment.name, Assessment.assessment_type, 
            Assessment.date, Assessment.max_score
        ).order_by(Class.name, Subject.name, Assessment.date.desc())
        
        # Apply filters
        if class_id:
            query = query.filter(Class.id == class_id)
        if subject_id:
            query = query.filter(Subject.id == subject_id)
        if assessment_type:
            query = query.filter(Assessment.assessment_type == assessment_type)
        if is_cbc is not None:
            is_cbc_bool = is_cbc.lower() == 'true'
            query = query.filter(Assessment.is_cbc == is_cbc_bool)
        
        # For teachers, only show their own classes and subjects
        if current_user.role == 'teacher':
            query = query.filter(or_(
                Class.class_teacher_id == current_user.id,
                and_(
                    Subject.id.in_([ts.subject_id for ts in current_user.taught_subjects]),
                    Class.id.in_([ts.class_id for ts in current_user.taught_subjects])
                )
            ))
        
        results = query.all()
        
        # Prepare report data
        report_data = []
        for result in results:
            report_data.append({
                "class_id": result.class_id,
                "class_name": result.class_name,
                "stream": result.stream,
                "subject_id": result.subject_id,
                "subject_name": result.subject_name,
                "assessment_id": result.assessment_id,
                "assessment_name": result.assessment_name,
                "assessment_type": result.assessment_type,
                "date": result.date.isoformat() if result.date else None,
                "max_score": result.max_score,
                "record_count": result.record_count,
                "average_score": round(float(result.average_score), 2) if result.average_score else None,
                "highest_score": float(result.highest_score) if result.highest_score else None,
                "lowest_score": float(result.lowest_score) if result.lowest_score else None
            })
        
        # Handle different output formats
        if format == 'csv':
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['Class ID', 'Class Name', 'Stream', 'Subject ID', 'Subject Name', 
                         'Assessment ID', 'Assessment Name', 'Type', 'Date', 'Max Score',
                         'Records', 'Average', 'Highest', 'Lowest'])
            for row in report_data:
                cw.writerow([
                    row['class_id'],
                    row['class_name'],
                    row['stream'],
                    row['subject_id'],
                    row['subject_name'],
                    row['assessment_id'],
                    row['assessment_name'],
                    row['assessment_type'],
                    row['date'],
                    row['max_score'],
                    row['record_count'],
                    row['average_score'],
                    row['highest_score'],
                    row['lowest_score']
                ])
            output = si.getvalue()
            filename = generate_report_filename('class_performance_summary', 'csv')
            return output, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename={filename}'
            }
        else:
            return jsonify({
                "report_type": "class_performance_summary",
                "data": report_data
            }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@reports_bp.route('/reports/performance/student-details', methods=['GET'])
@jwt_required()
def get_student_performance_details():
    """Generate detailed performance report for students"""
    current_user = User.query.get(get_jwt_identity())
    
    # Only teachers, headteachers, and admin can access performance reports
    if current_user.role not in ['teacher', 'headteacher', 'admin']:
        return jsonify({"error": "Unauthorized access"}), 403
    
    class_id = request.args.get('class_id')
    student_id = request.args.get('student_id')
    subject_id = request.args.get('subject_id')
    format = request.args.get('format', 'json')  # json or csv
    
    try:
        # Base query
        query = db.session.query(
            Student.id.label('student_id'),
            Student.full_name,
            Student.admission_number,
            Class.id.label('class_id'),
            Class.name.label('class_name'),
            Class.stream,
            Subject.id.label('subject_id'),
            Subject.name.label('subject_name'),
            Assessment.id.label('assessment_id'),
            Assessment.name.label('assessment_name'),
            Assessment.assessment_type,
            Assessment.date,
            Assessment.max_score,
            StudentPerformance.score,
            StudentPerformance.competency_level,
            StudentPerformance.strand,
            StudentPerformance.sub_strand,
            StudentPerformance.comments
        ).join(Class, Student.class_id == Class.id
        ).join(StudentPerformance, Student.id == StudentPerformance.student_id
        ).join(Assessment, StudentPerformance.assessment_id == Assessment.id
        ).join(Subject, Assessment.subject_id == Subject.id
        ).order_by(Student.full_name, Subject.name, Assessment.date.desc())
        
        # Apply filters
        if class_id:
            query = query.filter(Class.id == class_id)
        if student_id:
            query = query.filter(Student.id == student_id)
        if subject_id:
            query = query.filter(Subject.id == subject_id)
        
        # For teachers, only show their own classes and subjects
        if current_user.role == 'teacher':
            query = query.filter(or_(
                Class.class_teacher_id == current_user.id,
                and_(
                    Subject.id.in_([ts.subject_id for ts in current_user.taught_subjects]),
                    Class.id.in_([ts.class_id for ts in current_user.taught_subjects])
                )
            ))
        
        results = query.all()
        
        # Prepare report data
        report_data = []
        for result in results:
            percentage = (result.score / result.max_score * 100) if result.score is not None and result.max_score > 0 else None
            report_data.append({
                "student_id": result.student_id,
                "student_name": result.full_name,
                "admission_number": result.admission_number,
                "class_id": result.class_id,
                "class_name": result.class_name,
                "stream": result.stream,
                "subject_id": result.subject_id,
                "subject_name": result.subject_name,
                "assessment_id": result.assessment_id,
                "assessment_name": result.assessment_name,
                "assessment_type": result.assessment_type,
                "date": result.date.isoformat() if result.date else None,
                "max_score": result.max_score,
                "score": result.score,
                "percentage": round(percentage, 2) if percentage is not None else None,
                "competency_level": result.competency_level,
                "strand": result.strand,
                "sub_strand": result.sub_strand,
                "comments": result.comments
            })
        
        # Handle different output formats
        if format == 'csv':
            si = StringIO()
            cw = csv.writer(si)
            cw.writerow(['Student ID', 'Student Name', 'Admission Number', 'Class ID', 'Class Name', 'Stream',
                         'Subject ID', 'Subject Name', 'Assessment ID', 'Assessment Name', 'Type', 'Date',
                         'Max Score', 'Score', 'Percentage', 'Competency Level', 'Strand', 'Sub-strand', 'Comments'])
            for row in report_data:
                cw.writerow([
                    row['student_id'],
                    row['student_name'],
                    row['admission_number'],
                    row['class_id'],
                    row['class_name'],
                    row['stream'],
                    row['subject_id'],
                    row['subject_name'],
                    row['assessment_id'],
                    row['assessment_name'],
                    row['assessment_type'],
                    row['date'],
                    row['max_score'],
                    row['score'],
                    row['percentage'],
                    row['competency_level'],
                    row['strand'],
                    row['sub_strand'],
                    row['comments']
                ])
            output = si.getvalue()
            filename = generate_report_filename('student_performance_details', 'csv')
            return output, 200, {
                'Content-Type': 'text/csv',
                'Content-Disposition': f'attachment; filename={filename}'
            }
        else:
            return jsonify({
                "report_type": "student_performance_details",
                "data": report_data
            }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ====================== STUDENT PROGRESS REPORTS ======================

@reports_bp.route('/reports/progress/student/<int:student_id>', methods=['GET'])
@jwt_required()
def get_student_progress_report(student_id):
    """Generate comprehensive progress report for a student"""
    current_user = User.query.get(get_jwt_identity())
    student = Student.query.get_or_404(student_id)
    
    # Check authorization - teacher can only access their own students
    if current_user.role == 'teacher':
        is_class_teacher = student.class_.class_teacher_id == current_user.id
        teaches_subject = any(ts.class_id == student.class_id for ts in current_user.taught_subjects)
        if not (is_class_teacher or teaches_subject):
            return jsonify({"error": "Unauthorized access"}), 403
    
    # Get attendance summary
    attendance_summary = db.session.query(
        func.count(AttendanceRecord.id).label('total_days'),
        func.sum(case([(AttendanceRecord.status == 'present', 1)], else_=0)).label('present_days')
    ).filter(AttendanceRecord.student_id == student_id).first()
    
    attendance_rate = (attendance_summary.present_days / attendance_summary.total_days * 100) if attendance_summary.total_days > 0 else 0
    
    # Get performance summary by subject
    performance_summary = db.session.query(
        Subject.id.label('subject_id'),
        Subject.name.label('subject_name'),
        func.count(StudentPerformance.id).label('assessment_count'),
        func.avg(StudentPerformance.score).label('average_score'),
        Assessment.max_score
    ).join(Assessment, StudentPerformance.assessment_id == Assessment.id
    ).join(Subject, Assessment.subject_id == Subject.id
    ).filter(StudentPerformance.student_id == student_id
    ).group_by(Subject.id, Subject.name, Assessment.max_score).all()
    
    subject_performance = []
    for result in performance_summary:
        subject_performance.append({
            "subject_id": result.subject_id,
            "subject_name": result.subject_name,
            "assessment_count": result.assessment_count,
            "average_score": round(float(result.average_score), 2) if result.average_score else None,
            "max_score": result.max_score,
            "average_percentage": round((result.average_score / result.max_score * 100), 2) if result.average_score and result.max_score > 0 else None
        })
    
    # Get recent assessments
    recent_assessments = db.session.query(
        Assessment.id.label('assessment_id'),
        Assessment.name,
        Assessment.assessment_type,
        Assessment.date,
        Subject.name.label('subject_name'),
        StudentPerformance.score,
        Assessment.max_score,
        StudentPerformance.competency_level,
        StudentPerformance.comments
    ).join(StudentPerformance, Assessment.id == StudentPerformance.assessment_id
    ).join(Subject, Assessment.subject_id == Subject.id
    ).filter(StudentPerformance.student_id == student_id
    ).order_by(Assessment.date.desc()).limit(5).all()
    
    recent_assessments_data = []
    for assessment in recent_assessments:
        recent_assessments_data.append({
            "assessment_id": assessment.assessment_id,
            "name": assessment.name,
            "type": assessment.assessment_type,
            "date": assessment.date.isoformat() if assessment.date else None,
            "subject": assessment.subject_name,
            "score": assessment.score,
            "max_score": assessment.max_score,
            "percentage": round((assessment.score / assessment.max_score * 100), 2) if assessment.score is not None and assessment.max_score > 0 else None,
            "competency_level": assessment.competency_level,
            "comments": assessment.comments
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
        "attendance": {
            "total_days": attendance_summary.total_days,
            "present_days": attendance_summary.present_days,
            "attendance_rate": round(attendance_rate, 2)
        },
        "subject_performance": subject_performance,
        "recent_assessments": recent_assessments_data
    }), 200