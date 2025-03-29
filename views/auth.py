from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt_identity,
    create_refresh_token
)
from flask_login import login_user, logout_user
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from models import db, User

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/register', methods=['POST'])
def register():
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
            is_active=True
        )
        new_user.set_password(data["password"])
        
        db.session.add(new_user)
        db.session.commit()

        # Ensure identity is a string for JWT
        access_token = create_access_token(
            identity=str(new_user.id),  # Convert to string
            additional_claims={
                'username': new_user.username,
                'role': new_user.role
            }
        )
        
        return jsonify({
            "message": "User registered successfully",
            "access_token": access_token,
            "user": {
                "id": new_user.id,
                "username": new_user.username,
                "role": new_user.role
            }
        }), 201

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({"error": "Email and password required"}), 400

    user = User.query.filter_by(email=data['email']).first()

    if not user or not user.check_password(data['password']):
        return jsonify({"error": "Invalid credentials"}), 401

    if not user.is_active:
        return jsonify({"error": "Account inactive"}), 403

    login_user(user, remember=True)
    user.last_login = datetime.utcnow()
    db.session.commit()

    # Ensure identity is a string for JWT
    access_token = create_access_token(
        identity=str(user.id),  # Convert to string
        additional_claims={
            'username': user.username,
            'role': user.role
        }
    )
    refresh_token = create_refresh_token(identity=str(user.id))  # Convert to string

    return jsonify({
        "message": "Login successful",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user.id,
            "username": user.username,
            "role": user.role
        }
    }), 200

@auth_bp.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    try:
        logout_user()
        return jsonify({"message": "Logged out successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    new_token = create_access_token(identity=str(current_user_id))  # Convert to string
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