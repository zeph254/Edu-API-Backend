from .auth import *
from .admin import *
from .academics import *
from .user import *
from .performance import *
from .reports import *
from .timetable import *
from .attendance import *
from .oauth import init_oauth

def create_app():
    app = Flask(__name__)
    init_oauth(app)
