from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from sqlalchemy import MetaData

metadata = MetaData()

db = SQLAlchemy(metadata=metadata)

user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id'), primary_key=True),
    db.Column('assigned_by', db.Integer, db.ForeignKey('users.id')),
    db.Column('assigned_at', db.DateTime, default=datetime.utcnow)
)

class Role(db.Model):
    """Role model for different user types (Teacher, Parent, Admin, etc.)"""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200))
    is_default = db.Column(db.Boolean, default=False)
    permissions = db.Column(db.String(500))  # Comma-separated permissions
    
    def has_permission(self, permission):
        return permission in self.permissions.split(',')

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_email_verified = db.Column(db.Boolean, default=False)
    email_verification_token = db.Column(db.String(100))
    email_verification_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Profile relationship (one-to-one)
    profile = db.relationship('UserProfile', back_populates='user', uselist=False, cascade='all, delete-orphan')
    
    # Relationships with Class
    classes_taught = db.relationship('Class', back_populates='teacher', foreign_keys='Class.class_teacher_id')
    
    # Relationships with StudentPerformance
    recorded_performances = db.relationship('StudentPerformance', back_populates='recorded_by_user')
    
    # Relationships with AttendanceSession
    recorded_attendances = db.relationship('AttendanceSession', back_populates='recorder')
    
    # Relationships with TeacherSubject
    taught_subjects = db.relationship('TeacherSubject', back_populates='teacher')
    
    # Roles relationship (many-to-many)
    roles = db.relationship('Role', 
                        secondary=user_roles,
                        primaryjoin=(user_roles.c.user_id == id),
                        secondaryjoin=(user_roles.c.role_id == Role.id),
                        backref=db.backref('users', lazy='dynamic'),
                        lazy='dynamic')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_role(self, role_name):
        return self.roles.filter_by(name=role_name).first() is not None

class UserProfile(db.Model):
    """Extended user profile information"""
    __tablename__ = 'user_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    address = db.Column(db.String(200))
    profile_picture = db.Column(db.String(255))  # Path to image
    account_type = db.Column(db.String(20))  # 'parent' or 'teacher'
    is_profile_complete = db.Column(db.Boolean, default=False)
    
    # Teacher-specific fields
    qualifications = db.Column(db.Text)
    subjects = db.Column(db.String(200))  # Comma-separated subjects
    
    # Parent-specific fields
    children_details = db.Column(db.Text)  # Could be JSON serialized
    
    # Relationship back to User
    user = db.relationship('User', back_populates='profile')
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

class Class(db.Model):
    """Class/grade level model (e.g., Grade 4, Form 2)"""
    __tablename__ = 'classes'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # e.g., "Grade 4"
    stream = db.Column(db.String(20))               # e.g., "A", "B" (optional)
    academic_year = db.Column(db.String(20))
    
    # Relationships
    class_teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    teacher = db.relationship('User', back_populates='classes_taught', foreign_keys=[class_teacher_id])
    
    # Other relationships
    students = db.relationship('Student', back_populates='class_')
    subjects = db.relationship('TeacherSubject', back_populates='class_')
    timetable_entries = db.relationship('Timetable', back_populates='class_')
    attendance_sessions = db.relationship('AttendanceSession', back_populates='class_')

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