# Live Chat

Este documento detalla los requisitos y el procedimiento de instalación para la aplicación **Live Chat** desarrollada con Flask.

## Requisitos previos

1. Python 3.7 o superior.
2. Sistema de gestión de paquetes `pip`.
3. Servidor de base de datos MySQL (configurado según los parámetros en el archivo `.env`).
4. Entorno virtual de Python (recomendado).

## Procedimiento de instalación

Sigue los pasos a continuación para implementar el proyecto en un nuevo sistema:

### 1. Obtención del código fuente

Clona el repositorio en tu estación de trabajo mediante el siguiente comando:

```bash
git clone https://github.com/estevanvivas/live-chat
cd live-chat
```

### 2. Configuración del entorno virtual

Crea y activa un entorno virtual para aislar las dependencias:

```sh
# En sistemas Windows
python -m venv venv
venv\Scripts\activate

# En sistemas macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Instalación de dependencias

Instala los componentes necesarios utilizando el archivo de requisitos:

```bash
pip install -r requirements.txt
```

### 4. Configuración del entorno

Crea un archivo `.env` en el directorio raíz con los siguientes parámetros de configuración:

```
SECRET_KEY=private_key
DB_USER=root
DB_PASSWORD=root
DB_HOST=localhost
DB_NAME=chat_db
```

### 5. Configuración de la base de datos

Configura un servidor de base de datos MySQL con los parámetros especificados en el archivo `.env`. Asegúrate de crear la base de datos indicada en `DB_NAME`.

### 6. Ejecución de la aplicación

Para iniciar la aplicación y permitir conexiones desde otros equipos en la red, ejecuta:

```bash
flask run --host=0.0.0.0
```

La aplicación estará disponible en `http://[dirección_IP]:5000`, donde `dirección_IP` corresponde a la dirección IP del ordenador donde se ejecuta la aplicación. Para conocer la dirección IP de su equipo, puede utilizar el comando `ipconfig` en Windows o `ifconfig` en sistemas Linux/macOS.

## Características principales

- Chat en tiempo real mediante WebSockets.
- Notificaciones de usuarios conectados/desconectados.
- Indicadores de escritura.
- Historial de mensajes.
- Lista de usuarios en línea.
