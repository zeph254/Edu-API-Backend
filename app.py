from flask import Flask
from models import db
from flask_migrate import Migrate



app = Flask(__name__)


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///school.db'


migrate = Migrate(app, db)
db.init_app(app)


@app.route('/')
def home():
    return "Welcome to the School Management System!"
