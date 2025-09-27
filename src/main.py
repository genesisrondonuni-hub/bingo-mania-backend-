import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_socketio import SocketIO
from src.models.user import db, Config, User
from src.routes.user import user_bp
from src.routes.auth import auth_bp
from src.routes.rooms import rooms_bp
from src.routes.game import game_bp
from src.routes.admin import admin_bp

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configuración
app.config['SECRET_KEY'] = 'bingo-mania-secret-key-2024'
app.config['JWT_SECRET_KEY'] = 'jwt-secret-key-bingo-mania-2024'

# Base de datos
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializar extensiones
db.init_app(app)
jwt = JWTManager(app)
cors = CORS(app, origins="*")
socketio = SocketIO(app, cors_allowed_origins="*")

# Registrar blueprints
app.register_blueprint(user_bp, url_prefix='/api')
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(rooms_bp, url_prefix='/api')
app.register_blueprint(game_bp, url_prefix='/api')
app.register_blueprint(admin_bp, url_prefix='/api')

# Crear tablas y datos iniciales
with app.app_context():
    db.create_all()
    
    # Crear configuración por defecto si no existe
    if not Config.query.first():
        default_config = Config()
        db.session.add(default_config)
        db.session.commit()
    
    # Crear usuario admin por defecto si no existe
    admin_user = User.query.filter_by(email='admin@bingomania.com').first()
    if not admin_user:
        admin_user = User(
            nombre='Administrador',
            apellido='Sistema',
            email='admin@bingomania.com',
            is_admin=True,
            tokens=10000
        )
        admin_user.set_password('admin123')
        db.session.add(admin_user)
        db.session.commit()

# Socket.IO Events
@socketio.on('connect')
def handle_connect():
    print('Cliente conectado')

@socketio.on('disconnect')
def handle_disconnect():
    print('Cliente desconectado')

@socketio.on('join_room')
def handle_join_room(data):
    room_id = data.get('room_id')
    if room_id:
        from flask_socketio import join_room
        join_room(f'room_{room_id}')
        print(f'Usuario se unió a la sala {room_id}')

@socketio.on('leave_room')
def handle_leave_room(data):
    room_id = data.get('room_id')
    if room_id:
        from flask_socketio import leave_room
        leave_room(f'room_{room_id}')
        print(f'Usuario salió de la sala {room_id}')

# Función para emitir actualizaciones de juego
def emit_game_update(room_id, data):
    socketio.emit('game_update', data, room=f'room_{room_id}')

def emit_number_called(room_id, number, called_numbers):
    socketio.emit('number_called', {
        'number': number,
        'called_numbers': called_numbers
    }, room=f'room_{room_id}')

def emit_game_ended(room_id, winner_data):
    socketio.emit('game_ended', winner_data, room=f'room_{room_id}')

# Rutas para servir el frontend
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "Frontend not deployed yet", 404

# Manejo de errores JWT
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    return {'error': 'Token expirado'}, 401

@jwt.invalid_token_loader
def invalid_token_callback(error):
    return {'error': 'Token inválido'}, 401

@jwt.unauthorized_loader
def missing_token_callback(error):
    return {'error': 'Token requerido'}, 401

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

