from flask import Flask, Blueprint, request, jsonify, current_app, url_for
from flask_jwt_extended import (
    create_access_token, jwt_required, get_jwt_identity,
    create_refresh_token, set_refresh_cookies, unset_jwt_cookies
)
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
import jwt
from models import db, User, UserProfile, Role
from .oauth import init_oauth, handle_oauth_callback, get_oauth_provider
from .email_service import send_verification_email, send_password_reset_email  # You'll need to implement these

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

def create_app():
    app = Flask(__name__)
    init_oauth(app)

# Helper functions
def create_verification_token(user):
    """Create email verification token"""
    return jwt.encode(
        {
            'user_id': user.id,
            'exp': datetime.utcnow() + timedelta(days=1)
        },
        current_app.config['SECRET_KEY'],
        algorithm='HS256'
    )

def verify_token(token):
    """Verify email verification token"""
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        return User.query.get(data['user_id'])
    except:
        return None

@auth_bp.route('/register', methods=['POST'])
def register():
    """Initial user registration with email"""
    data = request.get_json()
    
    required_fields = ['email', 'password']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Email and password are required"}), 400
    
    existing_user = User.query.filter_by(email=data['email']).first()
    if existing_user:
        # If user exists but hasn't completed registration, allow them to continue
        if not existing_user.is_email_verified or not existing_user.profile:
            return jsonify({
                "message": "Account exists but registration incomplete",
                "next_step": "verify_email" if not existing_user.is_email_verified else "complete_profile",
                "user_id": existing_user.id
            }), 200
        return jsonify({"error": "Email already registered"}), 409
    
    try:
        # Create user with unverified email
        new_user = User(
            email=data['email'],
            is_email_verified=False,
            is_active=True
        )
        new_user.set_password(data['password'])
        
        # Assign default 'unverified' role
        default_role = Role.query.filter_by(is_default=True).first()
        if default_role:
            new_user.roles.append(default_role)
        
        db.session.add(new_user)
        db.session.commit()
        
        # Generate verification token and send email
        verification_token = create_verification_token(new_user)
        new_user.email_verification_token = verification_token
        new_user.email_verification_sent_at = datetime.utcnow()
        db.session.commit()
        
        verification_url = url_for('auth.verify_email', token=verification_token, _external=True)
        send_verification_email(new_user.email, verification_url)
        
        return jsonify({
            "message": "Registration successful. Please check your email to verify your account.",
            "user_id": new_user.id,
            "next_step": "verify_email"
        }), 201
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
    
@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email"""
    data = request.get_json()
    if 'email' not in data:
        return jsonify({"error": "Email is required"}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({"error": "Email not found"}), 404
    
    if user.is_email_verified:
        return jsonify({"message": "Email already verified"}), 200
    
    try:
        verification_token = create_verification_token(user)
        user.email_verification_token = verification_token
        user.email_verification_sent_at = datetime.utcnow()
        db.session.commit()
        
        verification_url = url_for('auth.verify_email', token=verification_token, _external=True)
        send_verification_email(user.email, verification_url)
        
        return jsonify({
            "message": "Verification email resent successfully",
            "user_id": user.id
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/check-registration-status', methods=['POST'])
def check_registration_status():
    """Check where user is in registration process"""
    data = request.get_json()
    if 'email' not in data:
        return jsonify({"error": "Email is required"}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({"status": "not_registered"}), 200
    
    if not user.is_email_verified:
        return jsonify({
            "status": "unverified",
            "user_id": user.id,
            "next_step": "verify_email"
        }), 200
    
    if not user.profile:
        return jsonify({
            "status": "uncompleted_profile",
            "user_id": user.id,
            "next_step": "complete_profile"
        }), 200
    
    return jsonify({
        "status": "complete",
        "user_id": user.id
    }), 200    

@auth_bp.route('/verify-email/<token>', methods=['GET'])
def verify_email(token):
    """Verify user's email with token from email"""
    user = verify_token(token)
    if not user:
        return jsonify({"error": "Invalid or expired verification link"}), 400
    
    if user.is_email_verified:
        return jsonify({"message": "Email already verified"}), 200
    
    try:
        user.is_email_verified = True
        user.email_verification_token = None
        db.session.commit()
        
        return jsonify({
            "message": "Email verified successfully",
            "next_step": "complete_profile",
            "user_id": user.id
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/complete-profile', methods=['POST'])
@jwt_required()
def complete_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    if not user.is_email_verified:
        return jsonify({"error": "Please verify your email first"}), 403
    
    # Check if form data is multipart/form-data
    if 'file' in request.files:
        file = request.files['file']
    else:
        file = None
    
    data = request.form
    
    # Validate account type
    if 'account_type' not in data or data['account_type'] not in ['parent', 'teacher']:
        return jsonify({"error": "Invalid account type"}), 400
    
    try:
        # Create or update user profile
        profile = user.profile or UserProfile(user_id=user.id)
        
        # Common fields
        profile.first_name = data['first_name']
        profile.last_name = data['last_name']
        profile.phone = data.get('phone')
        profile.account_type = data['account_type']
        
        # Handle file upload
        if file and file.filename != '':
            upload_result = upload_image_to_cloudinary(file)
            profile.profile_picture_public_id = upload_result['public_id']
            profile.profile_picture_url = upload_result['url']
        
        # Handle account type specific fields
        if data['account_type'] == 'teacher':
            if not data.get('qualifications'):
                return jsonify({"error": "Qualifications are required for teachers"}), 400
            profile.qualifications = data['qualifications']
            profile.subjects = data.get('subjects', '')
            profile.is_profile_complete = False  # Teachers need admin approval
        else:  # Parent
            if not data.get('children_details'):
                return jsonify({"error": "Children details are required for parents"}), 400
            profile.children_details = data['children_details']
            profile.is_profile_complete = True  # Parents are auto-approved
        
        if not user.profile:
            user.profile = profile
        
        # Assign role based on account type
        role = Role.query.filter_by(name=data['account_type']).first()
        if role:
            user.roles.append(role)
        
        # Remove default 'unverified' role if it exists
        default_role = Role.query.filter_by(is_default=True).first()
        if default_role and default_role in user.roles:
            user.roles.remove(default_role)
        
        db.session.commit()
        
        # Send appropriate email
        from .email_service import send_welcome_email
        send_welcome_email(user.email, profile.account_type)
        
        return jsonify({
            "message": "Profile completed successfully",
            "status": "active" if profile.is_profile_complete else "pending_approval",
            "user_id": user.id,
            "account_type": profile.account_type,
            "profile_picture_url": profile.profile_picture_url,
            "next_steps": ["wait_for_approval"] if profile.account_type == 'teacher' else []
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login with email and password"""
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=data['email']).first()

    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not user.is_active:
        return jsonify({"error": "Account is inactive"}), 403
    
    # Allow login even if email isn't verified or profile isn't complete
    # but provide information about what needs to be completed
    response_data = {
        "message": "Login successful",
        "user_id": user.id,
        "email": user.email,
        "status": "active",
        "next_steps": []
    }
    
    if not user.is_email_verified:
        response_data["status"] = "unverified"
        response_data["next_steps"].append("verify_email")
    
    if not user.profile:
        response_data["status"] = "uncompleted_profile"
        response_data["next_steps"].append("complete_profile")
    elif not user.profile.is_profile_complete and user.profile.account_type == 'parent':
        response_data["status"] = "pending_approval"
        response_data["next_steps"].append("wait_for_approval")
    
    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()

    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    response = jsonify(response_data)
    response.set_cookie('access_token', access_token, httponly=True)
    set_refresh_cookies(response, refresh_token)
    return response, 200


@auth_bp.route('/login/<provider>', methods=['GET'])
def oauth_login(provider):
    """Initiate OAuth login for any provider"""
    valid_providers = ['google']  # Add others as needed
    if provider not in valid_providers:
        return jsonify({"error": "Invalid provider"}), 400
    
    oauth_provider = get_oauth_provider(provider)
    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)
    return oauth_provider.authorize_redirect(redirect_uri)



@auth_bp.route('/login/<provider>/callback', methods=['GET'])
def oauth_callback(provider):
    """Handle OAuth callback for any provider"""
    user, error = handle_oauth_callback(provider)
    if error:
        return jsonify({"error": error}), 400
    
    # Check if profile is complete
    if not user.profile:
        return jsonify({
            "message": "Authentication successful",
            "user_id": user.id,
            "next_step": "complete_profile"
        }), 200
    
    # Generate tokens
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))
    
    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """User logout"""
    try:
        logout_user()
        response = jsonify({"message": "Logged out successfully"})
        unset_jwt_cookies(response)
        return response, 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Refresh access token"""
    current_user_id = get_jwt_identity()
    new_token = create_access_token(identity=str(current_user_id))
    return jsonify({"access_token": new_token}), 200

@auth_bp.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity()
    user = User.query.get(int(current_user_id))
    return jsonify({
        "message": "Access granted",
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
    }), 200


# Add these routes to auth.py

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Initiate password reset process"""
    data = request.get_json()
    if 'email' not in data:
        return jsonify({"error": "Email is required"}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({"message": "If this email exists, a reset link has been sent"}), 200
    
    try:
        # Create reset token (expires in 1 hour)
        reset_token = jwt.encode(
            {
                'user_id': user.id,
                'exp': datetime.utcnow() + timedelta(hours=1)
            },
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        # Save token to user (you might want to add reset_token and reset_sent_at fields to User model)
        user.reset_token = reset_token
        user.reset_sent_at = datetime.utcnow()
        db.session.commit()
        
        # Send email
        reset_url = url_for('auth.reset_password', token=reset_token, _external=True)
        send_password_reset_email(user.email, reset_url)
        
        return jsonify({"message": "If this email exists, a reset link has been sent"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Handle password reset with token"""
    try:
        data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user = User.query.get(data['user_id'])
    except:
        return jsonify({"error": "Invalid or expired token"}), 400
    
    if not user or user.reset_token != token:
        return jsonify({"error": "Invalid or expired token"}), 400
    
    # Check if token is expired (1 hour)
    if (datetime.utcnow() - user.reset_sent_at) > timedelta(hours=1):
        return jsonify({"error": "Token has expired"}), 400
    
    data = request.get_json()
    if 'password' not in data:
        return jsonify({"error": "Password is required"}), 400
    
    try:
        user.set_password(data['password'])
        user.reset_token = None
        user.reset_sent_at = None
        db.session.commit()
        
        return jsonify({"message": "Password updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/change-password', methods=['POST'])
@jwt_required()
def change_password():
    """Change password for authenticated users"""
    current_user_id = get_jwt_identity()
    user = User.query.get_or_404(current_user_id)
    
    data = request.get_json()
    required_fields = ['current_password', 'new_password']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Current and new password are required"}), 400
    
    if not user.check_password(data['current_password']):
        return jsonify({"error": "Current password is incorrect"}), 401
    
    try:
        user.set_password(data['new_password'])
        db.session.commit()
        return jsonify({"message": "Password changed successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500    