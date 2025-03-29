from flask import Blueprint

timetable_bp = Blueprint('timetable_bp', __name__)


@timetable_bp.route('/timetable')
def timetable():
    return "Welcome to the School Management System!"