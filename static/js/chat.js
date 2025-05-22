const socket = io();
let typingTimer;
let username;
let connectedUsers = new Set();
let currentRoomId;

// Variables para gestionar solicitudes de chat
let pendingChatRequest = null;
let chatRequestModal = null;

document.addEventListener('DOMContentLoaded', () => {
    // Inicializar el modal de solicitud de chat
    chatRequestModal = new bootstrap.Modal(document.getElementById('chatRequestModal'));

    // Configurar botones de aceptar/rechazar solicitud
    document.getElementById('accept-chat-request').addEventListener('click', () => {
        if (pendingChatRequest) {
            socket.emit('accept_chat_request', pendingChatRequest);
            chatRequestModal.hide();
            pendingChatRequest = null;
        }
    });

    document.getElementById('reject-chat-request').addEventListener('click', () => {
        if (pendingChatRequest) {
            socket.emit('reject_chat_request', pendingChatRequest);
            chatRequestModal.hide();
            pendingChatRequest = null;
        }
    });
});

socket.on('init_data', (data) => {
    username = data.username;

    // Obtener el ID de la sala actual desde el input oculto
    const currentRoomInput = document.getElementById('current-room-id');
    if (currentRoomInput) {
        currentRoomId = parseInt(currentRoomInput.value);

        // Unirse a la sala actual
        socket.emit('join_room', { room_id: currentRoomId });
    }

    socket.emit('user_joined', {username});
    socket.emit('request_users_list');
    connectedUsers.add(username);
    updateUsersList();
});

socket.on('connect', () => {
    document.getElementById('connection-status').innerHTML = '<span class="status-indicator status-online"></span> Conectado';
});

socket.on('users_list', (users) => {
    connectedUsers = new Set(users);
    updateUsersList();
});

socket.on('disconnect', () => {
    document.getElementById('connection-status').innerHTML = '<span class="status-indicator status-offline"></span> Desconectado';
});

// Recibir mensajes de una sala específica
socket.on('room_messages', (data) => {
    // Limpiar los mensajes actuales si cambiamos de sala
    if (data.room_id === currentRoomId) {
        const chatBox = document.getElementById('chat-box');
        chatBox.innerHTML = '';

        // Mostrar los mensajes de la sala
        data.messages.forEach(msg => addMessage(msg));
    }
});

socket.on('broadcast_message', (msg) => {
    // Solo añadir mensaje si pertenece a la sala actual
    if (!msg.chat_room_id || msg.chat_room_id === currentRoomId) {
        addMessage(msg);
        if (msg.username !== username) {
            new Audio('../static/notification.mp3').play();
        }
    }
});

socket.on('user_joined_broadcast', (data) => {
    // Ya no mostramos mensajes de conexión
    connectedUsers.add(data.username);
    updateUsersList();
});

socket.on('user_disconnected', (data) => {
    // Ya no mostramos mensajes de desconexión
    connectedUsers.delete(data.username);
    updateUsersList();
});

socket.on('user_typing', (data) => {
    // Solo mostrar "está escribiendo" si es de la sala actual
    if (data.username !== username && data.room_id === currentRoomId) {
        const typingStatus = document.getElementById('typing-status');
        typingStatus.innerHTML = `<i class="fas fa-keyboard me-1"></i>${data.username} está escribiendo...`;
        typingStatus.style.opacity = "1";

        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => {
            typingStatus.style.opacity = "0";
            setTimeout(() => {
                typingStatus.textContent = '';
            }, 300);
        }, 2000);
    }
});

document.getElementById('message-form').addEventListener('submit', (e) => {
    e.preventDefault();
    const message = document.getElementById('message').value.trim();
    const roomId = currentRoomId;

    if (message && roomId) {
        socket.emit('new_message', {
            text: message,
            room_id: roomId
        });
        document.getElementById('message').value = '';
    }
});

document.getElementById('message').addEventListener('input', () => {
    socket.emit('typing', {
        username,
        room_id: currentRoomId
    });
});

document.getElementById('message').addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        document.getElementById('message-form').dispatchEvent(new Event('submit'));
    }
});

function updateUsersList() {
    const usersListContainer = document.getElementById('other-users');
    usersListContainer.innerHTML = '';

    connectedUsers.forEach(user => {
        if (user !== username) {
            const userItem = document.createElement('div');
            userItem.className = 'user-item d-flex align-items-center justify-content-between mb-2';

            // Parte izquierda: usuario y estado
            const userInfo = document.createElement('div');
            userInfo.className = 'd-flex align-items-center';
            userInfo.innerHTML = `
                <span class="status-indicator status-online"></span>
                <span>${user}</span>
            `;

            // Parte derecha: botón para iniciar chat
            const actionButtons = document.createElement('div');
            const chatButton = document.createElement('button');
            chatButton.className = 'btn btn-sm btn-outline-primary ms-2';
            chatButton.innerHTML = '<i class="fas fa-comment"></i>';
            chatButton.addEventListener('click', () => requestDirectChat(user));

            actionButtons.appendChild(chatButton);

            // Agregar ambas partes al elemento principal
            userItem.appendChild(userInfo);
            userItem.appendChild(actionButtons);

            usersListContainer.appendChild(userItem);
        }
    });
}

// Función para solicitar un chat directo
function requestDirectChat(targetUser) {
    socket.emit('request_direct_chat', {
        target_username: targetUser
    });
}

function addMessage(msg) {
    const chatBox = document.getElementById('chat-box');
    const messageElement = document.createElement('div');

    const sanitize = (str) => {
        const temp = document.createElement('div');
        temp.textContent = str;
        return temp.innerHTML;
    };

    const sanitizedUsername = sanitize(msg.username);
    const sanitizedText = sanitize(msg.text);
    const isMyMessage = msg.username === username;

    const timestamp = msg.time ? new Date(msg.time) : new Date();
    const timeFormatted = timestamp.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit'});

    messageElement.className = `p-3 m-3 ${isMyMessage ? 'my-message ms-auto' : 'other-message me-auto'}`;
    messageElement.style.maxWidth = '70%';

    if (isMyMessage) {
        messageElement.innerHTML = `
            <div>${sanitizedText}</div>
            <div class="text-end small mt-1 opacity-75">${timeFormatted}</div>
        `;
    } else {
        messageElement.innerHTML = `
            <div class="fw-bold">${sanitizedUsername}</div>
            <div>${sanitizedText}</div>
            <div class="text-end small mt-1 opacity-75">${timeFormatted}</div>
        `;
    }

    chatBox.appendChild(messageElement);
    chatBox.scrollTop = chatBox.scrollHeight;
}

const toggleUsersButton = document.getElementById('toggle-users');
if (toggleUsersButton) {
    toggleUsersButton.addEventListener('click', () => {
        alert('Lista de usuarios conectados: ' + Array.from(connectedUsers).join(', '));
    });
}

// Recibir solicitud de chat
socket.on('chat_request', (data) => {
    pendingChatRequest = data;
    document.getElementById('chat-request-message').textContent =
        `${data.from_username} desea iniciar un chat contigo. ¿Aceptas?`;
    chatRequestModal.show();

    // Reproducir sonido de notificación
    new Audio('../static/notification.mp3').play();
});

// Recibir respuesta a solicitud de chat
socket.on('chat_request_accepted', (data) => {
    // Si la solicitud es para el usuario actual (el que inició o el que aceptó)
    if (data.from_username === username || data.target_username === username) {
        // Redireccionar al nuevo chat
        window.location.href = `/chat/${data.room_id}`;
    }
});

// Actualizar la lista de chats sin recargar la página
socket.on('update_chat_list_response', (data) => {
    // Obtener el contenedor de la lista de chats
    const chatRoomsList = document.getElementById('chat-rooms-list');
    if (!chatRoomsList) return;

    // Limpiar la lista actual
    chatRoomsList.innerHTML = '';

    // Añadir cada sala a la lista
    data.chat_rooms.forEach(room => {
        const roomItem = document.createElement('a');
        roomItem.href = `/chat/${room.id}`;
        roomItem.className = `chat-room-item d-flex align-items-center mb-2 text-decoration-none ${room.id === currentRoomId ? 'active' : ''}`;

        let roomIcon = '';
        if (room.type === 'general') {
            roomIcon = '<i class="fas fa-globe"></i>';
        } else if (room.type === 'direct') {
            roomIcon = '<i class="fas fa-user"></i>';
        } else if (room.type === 'group') {
            roomIcon = '<i class="fas fa-users"></i>';
        }

        roomItem.innerHTML = `
            <span class="chat-icon me-2">
                ${roomIcon}
            </span>
            <span class="chat-name">${room.name}</span>
        `;

        chatRoomsList.appendChild(roomItem);
    });
});

socket.on('chat_request_rejected', (data) => {
    alert(`${data.target_username} ha rechazado tu solicitud de chat.`);
});

// Cuando se recibe una señal para actualizar la lista de chats, solicitar la lista actualizada
socket.on('update_chat_list', () => {
    socket.emit('update_chat_list');
});

