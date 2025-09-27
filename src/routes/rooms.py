from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, Room, Game, Carton, Config
from datetime import datetime
import random

rooms_bp = Blueprint('rooms', __name__)

def generate_bingo_card():
    """Genera un cartón de bingo aleatorio"""
    # Columnas B(1-15), I(16-30), N(31-45), G(46-60), O(61-75)
    card = []
    
    # Columna B
    b_numbers = random.sample(range(1, 16), 5)
    # Columna I
    i_numbers = random.sample(range(16, 31), 5)
    # Columna N
    n_numbers = random.sample(range(31, 46), 5)
    # Columna G
    g_numbers = random.sample(range(46, 61), 5)
    # Columna O
    o_numbers = random.sample(range(61, 76), 5)
    
    # Crear matriz 5x5
    for row in range(5):
        card_row = [
            b_numbers[row],
            i_numbers[row],
            n_numbers[row] if row != 2 else 0,  # Centro libre
            g_numbers[row],
            o_numbers[row]
        ]
        card.append(card_row)
    
    return card

def create_new_room():
    """Crea una nueva sala automáticamente"""
    # Obtener el número de la última sala
    last_room = Room.query.order_by(Room.numero_sala.desc()).first()
    next_number = (last_room.numero_sala + 1) if last_room else 1
    
    # Crear nueva sala
    room = Room(numero_sala=next_number)
    db.session.add(room)
    
    # Crear juego asociado
    game = Game(room_id=room.id)
    db.session.add(game)
    
    db.session.commit()
    return room

@rooms_bp.route('/rooms', methods=['GET'])
@jwt_required()
def get_rooms():
    """Obtener todas las salas disponibles"""
    try:
        rooms = Room.query.order_by(Room.numero_sala.desc()).limit(20).all()
        
        # Si no hay salas o todas están terminadas, crear una nueva
        if not rooms or all(room.estado == 'terminada' for room in rooms):
            new_room = create_new_room()
            rooms = [new_room] + rooms
        
        rooms_data = []
        for room in rooms:
            room_dict = room.to_dict()
            # Agregar información del juego actual
            current_game = Game.query.filter_by(room_id=room.id).order_by(Game.id.desc()).first()
            if current_game:
                room_dict['game'] = current_game.to_dict()
            rooms_data.append(room_dict)
        
        return jsonify({'rooms': rooms_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@rooms_bp.route('/rooms/<int:room_id>', methods=['GET'])
@jwt_required()
def get_room(room_id):
    """Obtener información de una sala específica"""
    try:
        room = Room.query.get(room_id)
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        room_dict = room.to_dict()
        
        # Agregar información del juego actual
        current_game = Game.query.filter_by(room_id=room.id).order_by(Game.id.desc()).first()
        if current_game:
            room_dict['game'] = current_game.to_dict()
        
        # Agregar cartones del usuario actual
        user_id = get_jwt_identity()
        user_cartones = Carton.query.filter_by(user_id=user_id, room_id=room.id).all()
        room_dict['user_cartones'] = [carton.to_dict() for carton in user_cartones]
        
        return jsonify({'room': room_dict}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@rooms_bp.route('/rooms/<int:room_id>/join', methods=['POST'])
@jwt_required()
def join_room(room_id):
    """Unirse a una sala"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        if room.estado not in ['abierta', 'llena']:
            return jsonify({'error': 'No se puede unir a esta sala'}), 400
        
        # Verificar si el usuario ya está en la sala
        existing_carton = Carton.query.filter_by(user_id=user_id, room_id=room_id).first()
        if existing_carton:
            return jsonify({'message': 'Ya estás en esta sala'}), 200
        
        # Verificar capacidad
        if room.jugadores_actuales >= room.jugadores_maximo:
            room.estado = 'llena'
            db.session.commit()
            return jsonify({'error': 'Sala llena'}), 400
        
        return jsonify({'message': 'Unido a la sala exitosamente'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@rooms_bp.route('/rooms/<int:room_id>/buy-carton', methods=['POST'])
@jwt_required()
def buy_carton(room_id):
    """Comprar cartón para una sala"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        if room.estado not in ['abierta', 'llena']:
            return jsonify({'error': 'No se pueden comprar cartones en esta sala'}), 400
        
        # Obtener configuración
        config = Config.query.first()
        if not config:
            # Crear configuración por defecto
            config = Config()
            db.session.add(config)
            db.session.commit()
        
        # Verificar tokens suficientes
        if user.tokens < config.costo_carton:
            return jsonify({'error': 'Tokens insuficientes'}), 400
        
        # Verificar límite de cartones por usuario (máximo 4)
        user_cartones_count = Carton.query.filter_by(user_id=user_id, room_id=room_id).count()
        if user_cartones_count >= 4:
            return jsonify({'error': 'Máximo 4 cartones por sala'}), 400
        
        # Generar cartón
        card_numbers = generate_bingo_card()
        
        # Crear cartón
        carton = Carton(
            user_id=user_id,
            room_id=room_id
        )
        carton.set_numeros(card_numbers)
        carton.set_numeros_marcados([])
        
        # Descontar tokens
        user.tokens -= config.costo_carton
        
        # Agregar al pozo
        premio_amount = config.costo_carton * (config.porcentaje_premio / 100)
        room.pozo_acumulado += premio_amount
        
        # Actualizar contadores
        if user_cartones_count == 0:  # Primera vez que se une a la sala
            room.jugadores_actuales += 1
        
        # Actualizar juego
        current_game = Game.query.filter_by(room_id=room.id).order_by(Game.id.desc()).first()
        if current_game:
            current_game.cartones_vendidos += 1
        
        # Verificar si la sala está llena
        if room.jugadores_actuales >= room.jugadores_maximo:
            room.estado = 'llena'
        
        db.session.add(carton)
        db.session.commit()
        
        return jsonify({
            'message': 'Cartón comprado exitosamente',
            'carton': carton.to_dict(),
            'user_tokens': user.tokens,
            'room_pozo': room.pozo_acumulado
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@rooms_bp.route('/rooms/<int:room_id>/cartones', methods=['GET'])
@jwt_required()
def get_user_cartones(room_id):
    """Obtener cartones del usuario en una sala"""
    try:
        user_id = get_jwt_identity()
        cartones = Carton.query.filter_by(user_id=user_id, room_id=room_id).all()
        
        return jsonify({
            'cartones': [carton.to_dict() for carton in cartones]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@rooms_bp.route('/rooms/<int:room_id>/leave', methods=['POST'])
@jwt_required()
def leave_room(room_id):
    """Salir de una sala (solo si no ha empezado el juego)"""
    try:
        user_id = get_jwt_identity()
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        if room.estado == 'en_juego':
            return jsonify({'error': 'No se puede salir durante el juego'}), 400
        
        # Eliminar cartones del usuario
        user_cartones = Carton.query.filter_by(user_id=user_id, room_id=room_id).all()
        
        if not user_cartones:
            return jsonify({'message': 'No estás en esta sala'}), 200
        
        # Obtener configuración para reembolso
        config = Config.query.first()
        user = User.query.get(user_id)
        
        # Reembolsar tokens
        refund_amount = len(user_cartones) * config.costo_carton
        user.tokens += refund_amount
        
        # Reducir pozo
        premio_amount = refund_amount * (config.porcentaje_premio / 100)
        room.pozo_acumulado -= premio_amount
        
        # Eliminar cartones
        for carton in user_cartones:
            db.session.delete(carton)
        
        # Actualizar contadores
        room.jugadores_actuales -= 1
        
        # Actualizar juego
        current_game = Game.query.filter_by(room_id=room.id).order_by(Game.id.desc()).first()
        if current_game:
            current_game.cartones_vendidos -= len(user_cartones)
        
        # Actualizar estado de la sala
        if room.estado == 'llena' and room.jugadores_actuales < room.jugadores_maximo:
            room.estado = 'abierta'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Saliste de la sala exitosamente',
            'refund': refund_amount,
            'user_tokens': user.tokens
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

