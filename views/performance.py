from flask import Blueprint

performance_bp = Blueprint('performance_bp', __name__)


@performance_bp.route('/performance')
def performance():
    return "Welcome to the School Management System!"