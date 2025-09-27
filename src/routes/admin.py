from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, Room, Game, Carton, Config, SolicitudRetiro
from datetime import datetime

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """Decorador para verificar permisos de administrador"""
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        if not user or not user.is_admin:
            return jsonify({'error': 'Acceso denegado. Se requieren permisos de administrador'}), 403
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@admin_bp.route('/admin/login', methods=['POST'])
@jwt_required()
def admin_login():
    """Verificar credenciales de administrador"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        data = request.get_json()
        admin_password = data.get('admin_password')
        
        # Contraseña de administrador hardcodeada (en producción usar variables de entorno)
        if admin_password != 'admin123':
            return jsonify({'error': 'Contraseña de administrador incorrecta'}), 401
        
        # Marcar usuario como admin
        user.is_admin = True
        db.session.commit()
        
        return jsonify({
            'message': 'Acceso de administrador concedido',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/config', methods=['GET'])
@jwt_required()
@admin_required
def get_config():
    """Obtener configuración del sistema"""
    try:
        config = Config.query.first()
        if not config:
            # Crear configuración por defecto
            config = Config()
            db.session.add(config)
            db.session.commit()
        
        return jsonify({'config': config.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/config', methods=['PUT'])
@jwt_required()
@admin_required
def update_config():
    """Actualizar configuración del sistema"""
    try:
        config = Config.query.first()
        if not config:
            config = Config()
            db.session.add(config)
        
        data = request.get_json()
        
        # Actualizar campos
        if 'token_bs' in data:
            config.token_bs = float(data['token_bs'])
        if 'token_dolares' in data:
            config.token_dolares = float(data['token_dolares'])
        if 'costo_carton' in data:
            config.costo_carton = int(data['costo_carton'])
        if 'porcentaje_premio' in data:
            config.porcentaje_premio = int(data['porcentaje_premio'])
        if 'velocidad_juego' in data:
            config.velocidad_juego = int(data['velocidad_juego'])
        
        config.fecha_actualizacion = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Configuración actualizada exitosamente',
            'config': config.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/users', methods=['GET'])
@jwt_required()
@admin_required
def get_users():
    """Obtener lista de usuarios"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        users = User.query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            'users': [user.to_dict() for user in users.items],
            'total': users.total,
            'pages': users.pages,
            'current_page': page
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/users/<int:user_id>/tokens', methods=['PUT'])
@jwt_required()
@admin_required
def update_user_tokens(user_id):
    """Actualizar tokens de un usuario"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        data = request.get_json()
        action = data.get('action')  # 'add' o 'set'
        amount = data.get('amount', 0)
        
        if action == 'add':
            user.tokens += amount
        elif action == 'set':
            user.tokens = amount
        else:
            return jsonify({'error': 'Acción inválida. Use "add" o "set"'}), 400
        
        db.session.commit()
        
        return jsonify({
            'message': 'Tokens actualizados exitosamente',
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/solicitudes', methods=['GET'])
@jwt_required()
@admin_required
def get_solicitudes_retiro():
    """Obtener solicitudes de retiro"""
    try:
        estado = request.args.get('estado', 'pendiente')
        
        solicitudes = SolicitudRetiro.query.filter_by(estado=estado).order_by(
            SolicitudRetiro.fecha_solicitud.desc()
        ).all()
        
        return jsonify({
            'solicitudes': [solicitud.to_dict() for solicitud in solicitudes]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/solicitudes/<int:solicitud_id>', methods=['PUT'])
@jwt_required()
@admin_required
def procesar_solicitud_retiro(solicitud_id):
    """Procesar solicitud de retiro"""
    try:
        solicitud = SolicitudRetiro.query.get(solicitud_id)
        if not solicitud:
            return jsonify({'error': 'Solicitud no encontrada'}), 404
        
        data = request.get_json()
        nuevo_estado = data.get('estado')
        notas = data.get('notas', '')
        
        if nuevo_estado not in ['aprobado', 'rechazado']:
            return jsonify({'error': 'Estado inválido'}), 400
        
        # Si se rechaza, devolver tokens al usuario
        if nuevo_estado == 'rechazado':
            user = User.query.get(solicitud.user_id)
            user.tokens += solicitud.tokens
        
        solicitud.estado = nuevo_estado
        solicitud.fecha_procesamiento = datetime.utcnow()
        solicitud.notas_admin = notas
        
        db.session.commit()
        
        return jsonify({
            'message': f'Solicitud {nuevo_estado} exitosamente',
            'solicitud': solicitud.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/stats', methods=['GET'])
@jwt_required()
@admin_required
def get_stats():
    """Obtener estadísticas del sistema"""
    try:
        # Estadísticas básicas
        total_users = User.query.count()
        total_rooms = Room.query.count()
        total_games = Game.query.count()
        active_rooms = Room.query.filter(Room.estado.in_(['abierta', 'llena', 'en_juego'])).count()
        
        # Estadísticas de tokens
        total_tokens = db.session.query(db.func.sum(User.tokens)).scalar() or 0
        
        # Estadísticas de juegos
        completed_games = Game.query.filter_by(estado='finalizado').count()
        total_cartones = Carton.query.count()
        
        # Ingresos (aproximado)
        config = Config.query.first()
        if config:
            estimated_revenue = total_cartones * config.costo_carton * config.token_bs
        else:
            estimated_revenue = 0
        
        return jsonify({
            'stats': {
                'total_users': total_users,
                'total_rooms': total_rooms,
                'total_games': total_games,
                'active_rooms': active_rooms,
                'completed_games': completed_games,
                'total_cartones': total_cartones,
                'total_tokens_in_system': total_tokens,
                'estimated_revenue_bs': estimated_revenue
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/rooms/<int:room_id>/force-end', methods=['POST'])
@jwt_required()
@admin_required
def force_end_room(room_id):
    """Forzar finalización de una sala"""
    try:
        room = Room.query.get(room_id)
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        # Finalizar sala y juego
        room.estado = 'terminada'
        room.fecha_fin = datetime.utcnow()
        
        current_game = Game.query.filter_by(room_id=room_id).order_by(Game.id.desc()).first()
        if current_game:
            current_game.estado = 'finalizado'
            current_game.fecha_fin = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'message': 'Sala finalizada forzosamente'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@admin_bp.route('/admin/create-admin', methods=['POST'])
@jwt_required()
@admin_required
def create_admin():
    """Crear nuevo usuario administrador"""
    try:
        data = request.get_json()
        
        # Validar datos requeridos
        required_fields = ['nombre', 'apellido', 'email', 'password']
        for field in required_fields:
            if not data.get(field):
                return jsonify({'error': f'El campo {field} es requerido'}), 400
        
        # Verificar si el email ya existe
        if User.query.filter_by(email=data['email']).first():
            return jsonify({'error': 'El email ya está registrado'}), 400
        
        # Crear nuevo admin
        admin_user = User(
            nombre=data['nombre'],
            apellido=data['apellido'],
            email=data['email'],
            is_admin=True,
            tokens=1000  # Tokens iniciales para admin
        )
        admin_user.set_password(data['password'])
        
        db.session.add(admin_user)
        db.session.commit()
        
        return jsonify({
            'message': 'Administrador creado exitosamente',
            'admin': admin_user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

