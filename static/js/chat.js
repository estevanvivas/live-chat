const socket = io();
let typingTimer;
let username;
let connectedUsers = new Set();
let currentRoomId;

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
    const chatBox = document.getElementById('chat-box');
    const joinMessage = document.createElement('div');
    joinMessage.className = 'system-message';
    joinMessage.innerHTML = `<i class="fas fa-user-plus me-2 text-success"></i>${data.username} se ha unido al chat`;
    chatBox.appendChild(joinMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

    connectedUsers.add(data.username);
    updateUsersList();
});

socket.on('user_disconnected', (data) => {
    const chatBox = document.getElementById('chat-box');
    const leaveMessage = document.createElement('div');
    leaveMessage.className = 'system-message';
    leaveMessage.innerHTML = `<i class="fas fa-user-minus me-2 text-danger"></i>${data.username} ha salido del chat`;
    chatBox.appendChild(leaveMessage);
    chatBox.scrollTop = chatBox.scrollHeight;

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
            userItem.className = 'user-item d-flex align-items-center mb-2';
            userItem.innerHTML = `
                <span class="status-indicator status-online"></span>
                <span>${user}</span>
            `;
            usersListContainer.appendChild(userItem);
        }
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
