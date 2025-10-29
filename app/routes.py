from flask import Blueprint

main = Blueprint('main', __name__)

@main.route('/')
def home():
    return "Welkom bij je Flask-app met configuratie! 🎉"
