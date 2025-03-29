from flask import Blueprint


attendance_bp = Blueprint('attendance_bp', __name__)


@attendance_bp.route('/attendance')
def attendance():
    return "Welcome to the School Management System!"