print("✅ __init__.py wordt uitgevoerd en create_app bestaat!")

from flask import Flask
from .config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_caching import Cache   


db = SQLAlchemy()
cache = Cache() 

def create_app():
    app = Flask(__name__, template_folder='templates')
    app.config.from_object(Config)
    app.config["CACHE_TYPE"] = "simple"
    app.config["CACHE_DEFAULT_TIMEOUT"] = 3600

    db.init_app(app)
    cache.init_app(app)

    from .routes import main
    app.register_blueprint(main)

    return app


