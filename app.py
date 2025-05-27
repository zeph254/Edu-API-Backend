from flask import Flask, jsonify  # Make sure jsonify is imported
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from datetime import timedelta
from models import db, User, Role  # Ensure User model is imported

app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'
app.config['JWT_SECRET_KEY'] = 'knxsjnchbdhcvndjnksxnmdnj'  # Change in production
app.config['SECRET_KEY'] = 'cndjnksdjvnslcn.zndj'  # For session security
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=24)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Email Configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = 'ularezephaniah@gmail.com'  # Your email
app.config['MAIL_PASSWORD'] = 'wdiq clmy lcbp tjon'  # Your app password
app.config['MAIL_DEFAULT_SENDER'] = 'ularezephaniah@gmail.com'  # Your email
app.config['MAIL_DEFAULT_SENDER_NAME'] = 'School Management System'  # Sender name

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
jwt = JWTManager(app)
mail = Mail(app)  # Initialize Flask-Mail
# Assuming you have Flask-Mail configured

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = "auth.login"  # Must match blueprint name

# REQUIRED: User loader function
@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader callback"""
    return User.query.get(int(user_id))

# JWT Configuration
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return jsonify({"message": "Token has expired", "error": "token_expired"}), 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return jsonify({"message": "Invalid token", "error": "invalid_token"}), 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return jsonify({"message": "Missing authorization token", "error": "authorization_required"}), 401

# Import and register blueprints
from views.auth import auth_bp
from views.academics import academics_bp
from views.admin import admin_bp
from views.attendance import attendance_bp
from views.performance import performance_bp
from views.reports import reports_bp
from views.timetable import timetable_bp
from views.user import user_bp
 # Ensure mail is imported

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(academics_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(performance_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(timetable_bp)
app.register_blueprint(user_bp)

# Create tables

def create_default_roles():
    """Create default roles if they don't exist"""
    with app.app_context():
        default_roles = [
            {'name': 'admin', 'description': 'System administrator', 'is_default': False},
            {'name': 'teacher', 'description': 'School teacher', 'is_default': False},
            {'name': 'parent', 'description': 'Student parent', 'is_default': False},
            {'name': 'unverified', 'description': 'New unverified user', 'is_default': True}
        ]
        
        for role_data in default_roles:
            if not Role.query.filter_by(name=role_data['name']).first():
                role = Role(**role_data)
                db.session.add(role)
        
        db.session.commit()

# Create tables and default roles
with app.app_context():
    db.create_all()
    create_default_roles()

if __name__ == "__main__":
    app.run(debug=True)