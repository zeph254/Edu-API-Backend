from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, User
from werkzeug.security import generate_password_hash
from flask import request
from utils.cloudinary_utils import upload_image_to_cloudinary, delete_image_from_cloudinary

user_bp = Blueprint('user_bp', __name__)

@user_bp.route('/users', methods=['GET'])
@jwt_required()
def get_all_users():
    """Get all users (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    users = User.query.all()
    users_data = [{
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,
        'full_name': user.full_name,
        'is_active': user.is_active
    } for user in users]
    
    return jsonify(users_data), 200

@user_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Get a specific user's details"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    requested_user = User.query.get_or_404(user_id)
    
    # Users can view their own profile or admin can view any profile
    if current_user.id != user_id and current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    user_data = {
        'id': requested_user.id,
        'username': requested_user.username,
        'email': requested_user.email,
        'role': requested_user.role,
        'full_name': requested_user.full_name,
        'phone': requested_user.phone,
        'is_active': requested_user.is_active,
        'last_login': requested_user.last_login.isoformat() if requested_user.last_login else None
    }
    
    return jsonify(user_data), 200

@user_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
def update_user(user_id):
    """Update user information"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    user_to_update = User.query.get_or_404(user_id)
    
    # Users can update their own profile or admin can update any profile
    if current_user.id != user_id and current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    data = request.get_json()
    
    # Prevent non-admins from changing roles or active status
    if current_user.role != 'admin':
        if 'role' in data or 'is_active' in data:
            return jsonify({"error": "Only admin can change role or active status"}), 403
    
    # Update fields
    if 'username' in data:
        if User.query.filter(User.username == data['username'], User.id != user_id).first():
            return jsonify({"error": "Username already in use"}), 400
        user_to_update.username = data['username']
    
    if 'email' in data:
        if User.query.filter(User.email == data['email'], User.id != user_id).first():
            return jsonify({"error": "Email already in use"}), 400
        user_to_update.email = data['email']
    
    if 'full_name' in data:
        user_to_update.full_name = data['full_name']
    
    if 'phone' in data:
        user_to_update.phone = data['phone']
    
    if 'password' in data:
        user_to_update.set_password(data['password'])
    
    if 'role' in data and current_user.role == 'admin':
        user_to_update.role = data['role']
    
    if 'is_active' in data and current_user.role == 'admin':
        user_to_update.is_active = data['is_active']
    
    try:
        db.session.commit()
        return jsonify({"message": "User updated successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@user_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
def delete_user(user_id):
    """Delete a user account (admin only)"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    if current_user.role != 'admin':
        return jsonify({"error": "Unauthorized access"}), 403
    
    user_to_delete = User.query.get_or_404(user_id)
    
    # Prevent admin from deleting themselves
    if user_to_delete.id == current_user.id:
        return jsonify({"error": "Cannot delete your own account"}), 400
    
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        return jsonify({"message": "User deleted successfully"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@user_bp.route('/users/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Get the currently authenticated user's details"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    user_data = {
        'id': current_user.id,
        'username': current_user.username,
        'email': current_user.email,
        'role': current_user.role,
        'full_name': current_user.full_name,
        'phone': current_user.phone,
        'is_active': current_user.is_active,
        'last_login': current_user.last_login.isoformat() if current_user.last_login else None
    }
    
    return jsonify(user_data), 200

@user_bp.route('/users/<int:user_id>/profile-picture', methods=['POST'])
@jwt_required()
def upload_profile_picture(user_id):
    """Upload a profile picture for a user"""
    current_user_id = get_jwt_identity()
    
    # Check if user is updating their own profile or is admin
    if current_user_id != user_id and not User.query.get(current_user_id).has_role('admin'):
        return jsonify({"error": "Unauthorized access"}), 403
    
    user = User.query.get_or_404(user_id)
    
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    
    try:
        # Delete old picture if exists
        if user.profile and user.profile.profile_picture_public_id:
            delete_image_from_cloudinary(user.profile.profile_picture_public_id)
        
        # Upload new picture
        upload_result = upload_image_to_cloudinary(file)
        
        # Create profile if doesn't exist
        if not user.profile:
            user.profile = UserProfile(user_id=user.id)
            db.session.add(user.profile)
        
        # Update profile with new picture info
        user.profile.profile_picture_public_id = upload_result['public_id']
        user.profile.profile_picture_url = upload_result['url']
        
        db.session.commit()
        
        return jsonify({
            "message": "Profile picture updated successfully",
            "image_url": upload_result['url']
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@user_bp.route('/users/<int:user_id>/profile-picture', methods=['DELETE'])
@jwt_required()
def delete_profile_picture(user_id):
    """Delete a user's profile picture"""
    current_user_id = get_jwt_identity()
    
    # Check if user is updating their own profile or is admin
    if current_user_id != user_id and not User.query.get(current_user_id).has_role('admin'):
        return jsonify({"error": "Unauthorized access"}), 403
    
    user = User.query.get_or_404(user_id)
    
    if not user.profile or not user.profile.profile_picture_public_id:
        return jsonify({"error": "No profile picture to delete"}), 400
    
    try:
        delete_result = delete_image_from_cloudinary(user.profile.profile_picture_public_id)
        
        user.profile.profile_picture_public_id = None
        user.profile.profile_picture_url = None
        db.session.commit()
        
        return jsonify({
            "message": "Profile picture deleted successfully",
            "result": delete_result
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500