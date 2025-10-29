from flask import Flask
#from .models import db
from app.config import ConfigABC

def create_app():
    app = Flask(__name__)
    #app.config.from_object(ConfigABC)

    #db.init_app(app)

    #with app.app_context():
        #db.create_all()
        

    #from .routes import main
    #app.register_blueprint(main)

    return app

