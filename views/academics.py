from flask import Blueprint

academics_bp = Blueprint('academics_bp', __name__)


@academics_bp.route('/academics')
def academics():
    return "Welcome to the School Management System!"