from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import MetaData

metadata = MetaData()

db = SQLAlchemy(metadata=metadata)

class User(UserMixin, db.Model):
    """User model for all system users (teachers, admin, headteachers)"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), nullable=False)  # 'admin', 'headteacher', 'teacher'
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    taught_subjects = db.relationship('TeacherSubject', back_populates='teacher')
    class_teacher = db.relationship('Class', back_populates='class_teacher')
    recorded_attendances = db.relationship('AttendanceSession', back_populates='recorder')
    recorded_performances = db.relationship('StudentPerformance', back_populates='recorded_by_user')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Student(db.Model):
    """Student information model"""
    __tablename__ = 'students'
    
    id = db.Column(db.Integer, primary_key=True)
    admission_number = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    date_of_birth = db.Column(db.Date)
    gender = db.Column(db.String(10))
    parent_name = db.Column(db.String(100))
    parent_phone = db.Column(db.String(20))
    address = db.Column(db.Text)
    
    # Academic relationships
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    class_ = db.relationship('Class', back_populates='students')
    performances = db.relationship('StudentPerformance', back_populates='student')
    attendance_records = db.relationship('AttendanceRecord', back_populates='student')

class Class(db.Model):
    """Class/grade level model (e.g., Grade 4, Form 2)"""
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Grade 4"
    stream = db.Column(db.String(20))               # e.g., "A", "B" (optional)
    academic_year = db.Column(db.String(20))
    
    # Relationships
    class_teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    class_teacher = db.relationship('User', back_populates='class_teacher')
    students = db.relationship('Student', back_populates='class_')
    subjects = db.relationship('TeacherSubject', back_populates='class_')
    timetable_entries = db.relationship('Timetable', back_populates='class_')
    attendance_sessions = db.relationship('AttendanceSession', back_populates='class_')

class Subject(db.Model):
    """Academic subject model"""
    __tablename__ = 'subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Mathematics"
    code = db.Column(db.String(10), unique=True)     # e.g., "MATH101"
    is_core = db.Column(db.Boolean, default=False)
    
    # Relationships
    taught_in_classes = db.relationship('TeacherSubject', back_populates='subject')
    timetable_entries = db.relationship('Timetable', back_populates='subject')
    assessments = db.relationship('Assessment', back_populates='subject')
    attendance_sessions = db.relationship('AttendanceSession', back_populates='subject')

class TeacherSubject(db.Model):
    """Many-to-many relationship between teachers and subjects they teach in specific classes"""
    __tablename__ = 'teacher_subjects'
    
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    
    # Relationships
    teacher = db.relationship('User', back_populates='taught_subjects')
    subject = db.relationship('Subject', back_populates='taught_in_classes')
    class_ = db.relationship('Class', back_populates='subjects')

class Timetable(db.Model):
    """School timetable model"""
    __tablename__ = 'timetable'
    
    id = db.Column(db.Integer, primary_key=True)
    day = db.Column(db.String(10), nullable=False)  # Monday-Friday
    period = db.Column(db.Integer, nullable=False)  # 1-8
    room = db.Column(db.String(20))
    
    # Foreign keys
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    subject = db.relationship('Subject', back_populates='timetable_entries')
    class_ = db.relationship('Class', back_populates='timetable_entries')
    teacher = db.relationship('User')

class Assessment(db.Model):
    """Assessment/exam model"""
    __tablename__ = 'assessments'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Term 1 Math Exam"
    assessment_type = db.Column(db.String(30))       # "exam", "quiz", "project"
    date = db.Column(db.Date)
    max_score = db.Column(db.Integer)
    is_cbc = db.Column(db.Boolean, default=False)   # Competency-Based Curriculum flag
    
    # Foreign keys
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'), nullable=False)
    
    # Relationships
    subject = db.relationship('Subject', back_populates='assessments')
    performances = db.relationship('StudentPerformance', back_populates='assessment')

class StudentPerformance(db.Model):
    """Student performance/grade recording model"""
    __tablename__ = 'student_performances'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # For traditional grading
    score = db.Column(db.Float)
    
    # For CBC (Competency-Based Curriculum)
    competency_level = db.Column(db.String(20))  # e.g., "Exceeding", "Meeting", "Developing"
    strand = db.Column(db.String(50))           # CBC specific
    sub_strand = db.Column(db.String(50))       # CBC specific
    comments = db.Column(db.Text)
    
    # Foreign keys
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    assessment_id = db.Column(db.Integer, db.ForeignKey('assessments.id'), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    student = db.relationship('Student', back_populates='performances')
    assessment = db.relationship('Assessment', back_populates='performances')
    recorded_by_user = db.relationship('User', back_populates='recorded_performances')

class AttendanceSession(db.Model):
    """Attendance session model (when attendance was taken)"""
    __tablename__ = 'attendance_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    period = db.Column(db.Integer)       # For secondary schools with periods
    is_school_wide = db.Column(db.Boolean, default=False)  # For assembly/morning attendance
    
    # Foreign keys
    class_id = db.Column(db.Integer, db.ForeignKey('classes.id'))
    subject_id = db.Column(db.Integer, db.ForeignKey('subjects.id'))
    recorded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    class_ = db.relationship('Class', back_populates='attendance_sessions')
    subject = db.relationship('Subject', back_populates='attendance_sessions')
    recorder = db.relationship('User', back_populates='recorded_attendances')
    records = db.relationship('AttendanceRecord', back_populates='session', cascade='all, delete-orphan')

class AttendanceRecord(db.Model):
    """Individual student attendance records"""
    __tablename__ = 'attendance_records'
    
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(10), nullable=False)  # 'present', 'absent', 'late', 'excused'
    remarks = db.Column(db.String(100))                # e.g., "Sick with flu"
    
    # Foreign keys
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_sessions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    
    # Relationships
    session = db.relationship('AttendanceSession', back_populates='records')
    student = db.relationship('Student', back_populates='attendance_records')