from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import re

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}/{os.getenv('DB_NAME')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(app)

# Configuración de Flask-Login
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# User loader para Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Modelo de usuario para la base de datos
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


    def __init__(self, username, password):
        self.username = username
        self.password = password


    def __repr__(self):
        return f'<Usuario: {self.username}>'

# Almacenamiento temporal de mensajes
messages = []
connected_users = set()

# Crear las tablas al iniciar la aplicación
with app.app_context():
    db.create_all()

@app.route('/')
@login_required
def home():
    session['username'] = current_user.username
    return render_template('chat.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            session['username'] = username
            return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if len(username) < 5:
            flash('El nombre de usuario debe tener al menos 5 caracteres')
            return render_template('register.html')

        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            flash('El nombre de usuario solo puede contener letras, números, guiones bajos, puntos y guiones')
            return render_template('register.html')

        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres')
            return render_template('register.html')

        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            flash('El nombre de usuario ya existe')
        else:
            new_user = User(
                username=username,
                password=generate_password_hash(password)
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Usuario registrado correctamente')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('username', None)
    return redirect(url_for('login'))

@socketio.on('connect')
def handle_connect():
    print(f'Usuario conectado: {request.sid}')
    emit('messages_history', messages)

@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username:
        connected_users.discard(username)
        emit('user_disconnected', {'username': username}, broadcast=True)

@socketio.on('new_message')
def handle_new_message(data):
    message = {'username': data['username'], 'text': data['text'], 'time': data.get('time')}
    messages.append(message)

    emit('broadcast_message', message, broadcast=True)


@socketio.on('user_joined')
def handle_user_joined(data):
    username = data.get('username')
    if username:
        connected_users.add(username)
        emit('user_joined_broadcast', {'username': username}, broadcast=True, include_self=False)

@socketio.on('request_users_list')
def handle_users_list_request():
    emit('users_list', list(connected_users))

@socketio.on('typing')
def handle_typing(data):
    emit('user_typing', data, broadcast=True)

if __name__ == '__main__':
    socketio.run(app, debug=True)