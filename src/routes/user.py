from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import User, db, SolicitudRetiro, Config
from datetime import datetime

user_bp = Blueprint('user', __name__)

@user_bp.route('/users/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """Obtener perfil del usuario actual"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@user_bp.route('/users/solicitar-retiro', methods=['POST'])
@jwt_required()
def solicitar_retiro():
    """Solicitar retiro de tokens"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        data = request.get_json()
        tokens_a_retirar = data.get('tokens', 0)
        
        if tokens_a_retirar <= 0:
            return jsonify({'error': 'Cantidad de tokens inválida'}), 400
        
        if user.tokens < tokens_a_retirar:
            return jsonify({'error': 'Tokens insuficientes'}), 400
        
        # Verificar datos bancarios
        if not user.get_datos_bancarios():
            return jsonify({'error': 'Debe configurar sus datos bancarios primero'}), 400
        
        # Obtener configuración para calcular monto
        config = Config.query.first()
        if not config:
            return jsonify({'error': 'Configuración del sistema no encontrada'}), 500
        
        monto_bs = tokens_a_retirar * config.token_bs
        
        # Crear solicitud
        solicitud = SolicitudRetiro(
            user_id=user_id,
            tokens=tokens_a_retirar,
            monto_bs=monto_bs
        )
        
        # Descontar tokens temporalmente
        user.tokens -= tokens_a_retirar
        
        db.session.add(solicitud)
        db.session.commit()
        
        return jsonify({
            'message': 'Solicitud de retiro creada exitosamente',
            'solicitud': solicitud.to_dict(),
            'user_tokens': user.tokens
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@user_bp.route('/users/solicitudes-retiro', methods=['GET'])
@jwt_required()
def get_solicitudes_retiro():
    """Obtener solicitudes de retiro del usuario"""
    try:
        user_id = get_jwt_identity()
        solicitudes = SolicitudRetiro.query.filter_by(user_id=user_id).order_by(
            SolicitudRetiro.fecha_solicitud.desc()
        ).all()
        
        return jsonify({
            'solicitudes': [solicitud.to_dict() for solicitud in solicitudes]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@user_bp.route('/users/comprar-tokens', methods=['POST'])
@jwt_required()
def comprar_tokens():
    """Simular compra de tokens (en producción se integraría con pasarela de pago)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'Usuario no encontrado'}), 404
        
        data = request.get_json()
        monto_bs = data.get('monto_bs', 0)
        
        if monto_bs <= 0:
            return jsonify({'error': 'Monto inválido'}), 400
        
        # Obtener configuración
        config = Config.query.first()
        if not config:
            return jsonify({'error': 'Configuración del sistema no encontrada'}), 500
        
        # Calcular tokens a agregar
        tokens_a_agregar = int(monto_bs / config.token_bs)
        
        if tokens_a_agregar <= 0:
            return jsonify({'error': 'Monto insuficiente para comprar tokens'}), 400
        
        # Agregar tokens
        user.tokens += tokens_a_agregar
        db.session.commit()
        
        return jsonify({
            'message': f'Compra exitosa. Se agregaron {tokens_a_agregar} tokens',
            'tokens_agregados': tokens_a_agregar,
            'user_tokens': user.tokens,
            'monto_pagado': monto_bs
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@user_bp.route('/users/historial-juegos', methods=['GET'])
@jwt_required()
def get_historial_juegos():
    """Obtener historial de juegos del usuario"""
    try:
        user_id = get_jwt_identity()
        
        # Obtener cartones del usuario con información de las salas y juegos
        from src.models.user import Carton, Room, Game
        
        cartones = db.session.query(Carton, Room, Game).join(
            Room, Carton.room_id == Room.id
        ).join(
            Game, Room.id == Game.room_id
        ).filter(
            Carton.user_id == user_id,
            Game.estado == 'finalizado'
        ).order_by(Game.fecha_fin.desc()).limit(50).all()
        
        historial = []
        for carton, room, game in cartones:
            historial.append({
                'carton': carton.to_dict(),
                'room': room.to_dict(),
                'game': game.to_dict(),
                'es_ganador': carton.es_ganador,
                'premio': game.premio_ganador if carton.es_ganador else 0
            })
        
        return jsonify({'historial': historial}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@user_bp.route('/users/stats', methods=['GET'])
@jwt_required()
def get_user_stats():
    """Obtener estadísticas del usuario"""
    try:
        user_id = get_jwt_identity()
        
        from src.models.user import Carton, Game
        
        # Estadísticas básicas
        total_cartones = Carton.query.filter_by(user_id=user_id).count()
        cartones_ganadores = Carton.query.filter_by(user_id=user_id, es_ganador=True).count()
        
        # Juegos jugados
        juegos_jugados = db.session.query(Game).join(
            Carton, Game.room_id == Carton.room_id
        ).filter(
            Carton.user_id == user_id,
            Game.estado == 'finalizado'
        ).distinct().count()
        
        # Premios ganados
        premios_ganados = db.session.query(db.func.sum(Game.premio_ganador)).join(
            Carton, Game.room_id == Carton.room_id
        ).filter(
            Carton.user_id == user_id,
            Carton.es_ganador == True
        ).scalar() or 0
        
        # Porcentaje de victoria
        win_rate = (cartones_ganadores / total_cartones * 100) if total_cartones > 0 else 0
        
        return jsonify({
            'stats': {
                'total_cartones': total_cartones,
                'cartones_ganadores': cartones_ganadores,
                'juegos_jugados': juegos_jugados,
                'premios_ganados': premios_ganados,
                'win_rate': round(win_rate, 2)
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

