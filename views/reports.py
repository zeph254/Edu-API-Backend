from flask import Blueprint

reports_bp = Blueprint('reports_bp', __name__)


@reports_bp.route('/reports')
def reports():
    return "Welcome to the School Management System!"