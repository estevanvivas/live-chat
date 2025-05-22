from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from datetime import datetime
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

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

user_sessions = {}

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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())
    # Relaciones
    messages = db.relationship('Message', backref='sender', lazy=True)
    chat_rooms = db.relationship('UserChatRoom', back_populates='user')

    def __init__(self, username, password):
        self.username = username
        self.password = password

    def __repr__(self):
        return f'<Usuario: {self.username}>'


class ChatRoom(db.Model):
    __tablename__ = 'chat_rooms'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=True)
    room_type = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())

    # Relaciones
    messages = db.relationship('Message', backref='chat_room', lazy=True, cascade='all, delete-orphan')
    users = db.relationship('UserChatRoom', back_populates='chat_room', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ChatRoom: {self.name or "Sin nombre"} ({self.room_type})>'


# Modelo para mensajes
class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now())

    # Claves foráneas
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_rooms.id'), nullable=False)

    def __repr__(self):
        return f'<Message: {self.text[:20]}... por {self.sender_id}>'

    def to_dict(self):
        return {
            'id': self.id,
            'text': self.text,
            'username': self.sender.username,
            'time': self.created_at.isoformat(),
            'chat_room_id': self.chat_room_id
        }


# Tabla de relación entre usuarios y salas de chat
class UserChatRoom(db.Model):
    __tablename__ = 'user_chat_rooms'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    chat_room_id = db.Column(db.Integer, db.ForeignKey('chat_rooms.id'), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    last_read = db.Column(db.DateTime, default=lambda: datetime.now())

    # Relaciones
    user = db.relationship('User', back_populates='chat_rooms')
    chat_room = db.relationship('ChatRoom', back_populates='users')

    __table_args__ = (db.UniqueConstraint('user_id', 'chat_room_id'),)

    def __repr__(self):
        return f'<UserChatRoom: {self.user_id} en {self.chat_room_id}>'


# Almacenamiento temporal de mensajes
messages = []
connected_users = set()

# Crear las tablas al iniciar la aplicación
with app.app_context():
    db.create_all()

    # Asegurar que existe la sala de chat general
    general_chat = ChatRoom.query.filter_by(room_type='general').first()
    if not general_chat:
        general_chat = ChatRoom(name='General', room_type='general')
        db.session.add(general_chat)
        db.session.commit()


@app.route('/')
@login_required
def home():
    session['username'] = current_user.username
    # Obtener todas las salas de chat a las que pertenece el usuario
    user_rooms = UserChatRoom.query.filter_by(user_id=current_user.id).all()

    # Si el usuario no está en la sala general, añadirlo
    general_room = ChatRoom.query.filter_by(room_type='general').first()
    if general_room and not any(ur.chat_room_id == general_room.id for ur in user_rooms):
        user_general_room = UserChatRoom(user_id=current_user.id, chat_room_id=general_room.id)
        db.session.add(user_general_room)
        db.session.commit()
        user_rooms = UserChatRoom.query.filter_by(user_id=current_user.id).all()

    # Preparar datos para la plantilla
    chat_rooms = []
    for user_room in user_rooms:
        room = user_room.chat_room
        room_data = {
            'id': room.id,
            'name': room.name,
            'type': room.room_type
        }

        # Para chats directos, usar el nombre del otro usuario
        if room.room_type == 'direct':
            other_user = UserChatRoom.query.filter(
                UserChatRoom.chat_room_id == room.id,
                UserChatRoom.user_id != current_user.id
            ).first()
            if other_user:
                room_data['name'] = other_user.user.username

        chat_rooms.append(room_data)

    # Obtener todos los usuarios para la creación de chats directos
    all_users = User.query.filter(User.id != current_user.id).all()

    return render_template('chat.html', chat_rooms=chat_rooms, all_users=all_users, current_room_id=general_room.id)


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

        if len(username) > 20:
            flash('El nombre de usuario no puede tener más de 20 caracteres')
            return render_template('register.html')

        if not re.match(r'^[a-zA-Z0-9_.-]+$', username):
            flash('El nombre de usuario solo puede contener letras, números, guiones bajos, puntos y guiones')
            return render_template('register.html')

        if len(password) < 8:
            flash('La contraseña debe tener al menos 8 caracteres')
            return render_template('register.html')

        if len(password) > 20:
            flash('La contraseña no puede tener más de 20 caracteres')
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
    username = current_user.username

    if username in user_sessions:
        emit('user_disconnected', {'username': username}, broadcast=True, namespace='/')

        user_sessions.pop(username, None)
        connected_users.discard(username)

    logout_user()
    session.pop('username', None)

    return redirect(url_for('login'))


@app.route('/create_direct_chat/<int:user_id>', methods=['POST'])
@login_required
def create_direct_chat(user_id):
    other_user = User.query.get_or_404(user_id)

    direct_chat = None
    user_rooms = UserChatRoom.query.filter_by(user_id=current_user.id).all()

    for user_room in user_rooms:
        room = user_room.chat_room
        if room.room_type == 'direct':
            other_in_room = UserChatRoom.query.filter_by(
                user_id=other_user.id,
                chat_room_id=room.id
            ).first()

            if other_in_room:
                direct_chat = room
                break

    if not direct_chat:
        direct_chat = ChatRoom(
            name=f"Chat entre {current_user.username} y {other_user.username}",
            room_type='direct'
        )
        db.session.add(direct_chat)
        db.session.flush()

        user_room1 = UserChatRoom(user_id=current_user.id, chat_room_id=direct_chat.id)
        user_room2 = UserChatRoom(user_id=other_user.id, chat_room_id=direct_chat.id)

        db.session.add_all([user_room1, user_room2])
        db.session.commit()

    return redirect(url_for('home'))


@app.route('/create_group', methods=['POST'])
@login_required
def create_group():
    group_name = request.form.get('group_name')
    member_ids = request.form.getlist('member_ids')

    if not group_name or len(group_name) < 3:
        flash('El nombre del grupo debe tener al menos 3 caracteres')
        return redirect(url_for('home'))

    group_chat = ChatRoom(
        name=group_name,
        room_type='group'
    )
    db.session.add(group_chat)
    db.session.flush()

    creator_room = UserChatRoom(
        user_id=current_user.id,
        chat_room_id=group_chat.id,
        is_admin=True
    )
    db.session.add(creator_room)

    all_members = [current_user.id]

    for member_id in member_ids:
        member_id = int(member_id)
        if member_id != current_user.id:
            member_room = UserChatRoom(
                user_id=member_id,
                chat_room_id=group_chat.id
            )
            db.session.add(member_room)
            all_members.append(member_id)

    db.session.commit()

    for member_id in all_members:
        member = User.query.get(member_id)
        if member and member.username in user_sessions:
            for sid in user_sessions[member.username]:
                socketio.emit('update_chat_list', {}, room=sid)

    return redirect(url_for('home'))


@app.route('/chat/<int:room_id>')
@login_required
def chat_room(room_id):
    # Verificar que el usuario tiene acceso a esta sala
    user_room = UserChatRoom.query.filter_by(
        user_id=current_user.id,
        chat_room_id=room_id
    ).first_or_404()

    # Obtener todas las salas del usuario para el menú lateral
    user_rooms = UserChatRoom.query.filter_by(user_id=current_user.id).all()

    chat_rooms = []
    for ur in user_rooms:
        room = ur.chat_room
        room_data = {
            'id': room.id,
            'name': room.name,
            'type': room.room_type
        }

        if room.room_type == 'direct':
            other_user = UserChatRoom.query.filter(
                UserChatRoom.chat_room_id == room.id,
                UserChatRoom.user_id != current_user.id
            ).first()
            if other_user:
                room_data['name'] = other_user.user.username

        chat_rooms.append(room_data)

    # Obtener los mensajes de esta sala
    messages = Message.query.filter_by(chat_room_id=room_id).order_by(Message.created_at).all()
    room_messages = [msg.to_dict() for msg in messages]

    # Obtener todos los usuarios para la creación de chats directos
    all_users = User.query.filter(User.id != current_user.id).all()

    return render_template(
        'chat.html',
        chat_rooms=chat_rooms,
        all_users=all_users,
        current_room_id=room_id,
        room_messages=room_messages
    )


@socketio.on('connect')
def handle_connect():
    print(f'Usuario conectado: {request.sid}')
    username = session.get('username')
    user_id = current_user.id if current_user.is_authenticated else None

    if username:
        if username not in user_sessions:
            user_sessions[username] = []
        user_sessions[username].append(request.sid)
        connected_users.add(username)

    if user_id:
        user_rooms = UserChatRoom.query.filter_by(user_id=user_id).all()
        for user_room in user_rooms:
            socketio.server.enter_room(request.sid, f"room_{user_room.chat_room_id}")

    # Inicializar datos - solo para compatibilidad con la versión anterior
    emit('init_data', {
        'username': username,
        'messages': []  # Ya no enviamos todos los mensajes aquí
    })


@socketio.on('disconnect')
def handle_disconnect():
    username = session.get('username')
    if username:
        # Eliminar esta sesión específica de la lista de sesiones del usuario
        if username in user_sessions and request.sid in user_sessions[username]:
            user_sessions[username].remove(request.sid)
            # Si no quedan sesiones, eliminar el usuario de la lista de conectados
            if not user_sessions[username]:
                user_sessions.pop(username, None)
                connected_users.discard(username)
                emit('user_disconnected', {'username': username}, broadcast=True)


@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')
    if room_id and current_user.is_authenticated:
        # Verificar que el usuario tiene acceso a esta sala
        user_room = UserChatRoom.query.filter_by(
            user_id=current_user.id,
            chat_room_id=room_id
        ).first()

        if user_room:
            socketio.server.enter_room(request.sid, f"room_{room_id}")

            user_room.last_read = datetime.now()
            db.session.commit()

            # Obtener los mensajes de esta sala
            messages = Message.query.filter_by(chat_room_id=room_id).order_by(Message.created_at).all()
            room_messages = [msg.to_dict() for msg in messages]

            emit('room_messages', {
                'room_id': room_id,
                'messages': room_messages
            })


@socketio.on('new_message')
def handle_new_message(data):
    if not current_user.is_authenticated:
        return

    username = current_user.username
    text = data.get('text')
    room_id = data.get('room_id')

    if not text or not room_id:
        return

    # Verificar que el usuario tiene acceso a esta sala
    user_room = UserChatRoom.query.filter_by(
        user_id=current_user.id,
        chat_room_id=room_id
    ).first()

    if not user_room:
        return

    # Guardar el mensaje en la base de datos
    new_message = Message(
        text=text,
        sender_id=current_user.id,
        chat_room_id=room_id
    )
    db.session.add(new_message)
    db.session.commit()

    message_data = new_message.to_dict()

    emit('broadcast_message', message_data, room=f"room_{room_id}")

    user_room.last_read = datetime.now()
    db.session.commit()


@socketio.on('typing')
def handle_typing(data):
    room_id = data.get('room_id')
    if room_id and current_user.is_authenticated:
        emit('user_typing', {
            'username': current_user.username,
            'room_id': room_id
        }, room=f"room_{room_id}")


@socketio.on('user_joined')
def handle_user_joined(data):
    username = current_user.username if current_user.is_authenticated else None
    if username:
        connected_users.add(username)
        emit('user_joined_broadcast', {'username': username}, broadcast=True, include_self=False)


@socketio.on('request_users_list')
def handle_users_list_request():
    emit('users_list', list(connected_users))


@socketio.on('request_direct_chat')
def handle_chat_request(data):
    if not current_user.is_authenticated:
        return

    target_username = data.get('target_username')
    if not target_username:
        return

    target_user = User.query.filter_by(username=target_username).first()
    if not target_user:
        return

    existing_chat = None
    user_rooms = UserChatRoom.query.filter_by(user_id=current_user.id).all()

    for user_room in user_rooms:
        room = user_room.chat_room
        if room.room_type == 'direct':
            other_in_room = UserChatRoom.query.filter_by(
                user_id=target_user.id,
                chat_room_id=room.id
            ).first()

            if other_in_room:
                existing_chat = room
                break

    if existing_chat:
        emit('chat_request_accepted', {
            'room_id': existing_chat.id,
            'target_username': target_username
        })
        return

    if target_username in connected_users:
        if target_username in user_sessions and user_sessions[target_username]:
            target_found = False
            for target_sid in user_sessions[target_username]:
                emit('chat_request', {
                    'from_username': current_user.username,
                    'from_user_id': current_user.id,
                    'target_username': target_username,
                    'target_user_id': target_user.id
                }, room=target_sid)
                target_found = True

            if target_found:
                return

        emit('system_message', {
            'message': f'No se pudo enviar la solicitud a {target_username}.'
        })
    else:
        emit('system_message', {
            'message': f'El usuario {target_username} no está conectado actualmente.'
        })


@socketio.on('update_chat_list')
def handle_update_chat_list():
    if not current_user.is_authenticated:
        return

    user_rooms = UserChatRoom.query.filter_by(user_id=current_user.id).all()

    chat_rooms = []
    for user_room in user_rooms:
        room = user_room.chat_room
        room_data = {
            'id': room.id,
            'name': room.name,
            'type': room.room_type
        }

        if room.room_type == 'direct':
            other_user = UserChatRoom.query.filter(
                UserChatRoom.chat_room_id == room.id,
                UserChatRoom.user_id != current_user.id
            ).first()
            if other_user:
                room_data['name'] = other_user.user.username

        chat_rooms.append(room_data)

    emit('update_chat_list_response', {'chat_rooms': chat_rooms})


@socketio.on('accept_chat_request')
def handle_accept_chat_request(data):
    if not current_user.is_authenticated:
        return

    from_username = data.get('from_username')
    from_user_id = data.get('from_user_id')

    direct_chat = ChatRoom(
        name=f"Chat entre {from_username} y {current_user.username}",
        room_type='direct'
    )
    db.session.add(direct_chat)
    db.session.flush()

    user_room1 = UserChatRoom(user_id=from_user_id, chat_room_id=direct_chat.id)
    user_room2 = UserChatRoom(user_id=current_user.id, chat_room_id=direct_chat.id)

    db.session.add_all([user_room1, user_room2])
    db.session.commit()

    emit('chat_request_accepted', {
        'room_id': direct_chat.id,
        'target_username': current_user.username,
        'from_username': from_username
    }, room=request.sid)

    if from_username in user_sessions:
        for sid in user_sessions[from_username]:
            emit('chat_request_accepted', {
                'room_id': direct_chat.id,
                'target_username': current_user.username,
                'from_username': from_username
            }, room=sid)

    emit('update_chat_list', {}, room=request.sid)

    if from_username in user_sessions:
        for sid in user_sessions[from_username]:
            emit('update_chat_list', {}, room=sid)


@socketio.on('reject_chat_request')
def handle_reject_chat_request(data):
    if not current_user.is_authenticated:
        return

    from_username = data.get('from_username')

    if from_username in user_sessions:
        for sid in user_sessions[from_username]:
            emit('chat_request_rejected', {
                'target_username': current_user.username
            }, room=sid)


if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')
