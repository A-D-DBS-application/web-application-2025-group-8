from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

# Maak een database-instantie
db = SQLAlchemy()

def create_app():
    # Initialiseer de Flask-app
    app = Flask(__name__)
    app.config.from_object(Config)

    # Koppel de database aan de app
    db.init_app(app)

    # Maak tabellen aan (indien ze nog niet bestaan)
    with app.app_context():
        db.create_all()
        print("✅ Database connected and tables created successfully!")

    # Routes importeren (pas aan als je routes.py ergens anders zit)
    from .routes import main
    app.register_blueprint(main)

    return app

