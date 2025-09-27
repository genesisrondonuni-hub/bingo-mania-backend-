from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import db, User, Room, Game, Carton, Config
from datetime import datetime
import random
import threading
import time

game_bp = Blueprint('game', __name__)

# Variable global para controlar los juegos activos
active_games = {}

def check_bingo(carton_numeros, numeros_marcados):
    """Verifica si hay bingo en un cartón"""
    # Convertir a matriz 5x5
    card = carton_numeros
    marked = set(numeros_marcados)
    
    # Verificar filas
    for row in card:
        if all(num == 0 or num in marked for num in row):  # 0 es el centro libre
            return True
    
    # Verificar columnas
    for col in range(5):
        if all(card[row][col] == 0 or card[row][col] in marked for row in range(5)):
            return True
    
    # Verificar diagonales
    # Diagonal principal
    if all(card[i][i] == 0 or card[i][i] in marked for i in range(5)):
        return True
    
    # Diagonal secundaria
    if all(card[i][4-i] == 0 or card[i][4-i] in marked for i in range(5)):
        return True
    
    return False

def auto_mark_numbers(carton, called_numbers):
    """Marca automáticamente los números cantados en un cartón"""
    carton_numbers = carton.get_numeros()
    current_marked = set(carton.get_numeros_marcados())
    
    # Aplanar la matriz del cartón para facilitar la búsqueda
    flat_numbers = []
    for row in carton_numbers:
        flat_numbers.extend(row)
    
    # Marcar números que coincidan
    for number in called_numbers:
        if number in flat_numbers and number not in current_marked:
            current_marked.add(number)
    
    # Actualizar cartón
    carton.set_numeros_marcados(list(current_marked))
    return list(current_marked)

def run_game(room_id):
    """Ejecuta el juego automáticamente"""
    try:
        with db.session.begin():
            room = Room.query.get(room_id)
            game = Game.query.filter_by(room_id=room_id).order_by(Game.id.desc()).first()
            config = Config.query.first()
            
            if not room or not game or not config:
                return
            
            # Cambiar estado
            room.estado = 'en_juego'
            game.estado = 'en_progreso'
            game.fecha_inicio = datetime.utcnow()
            room.fecha_inicio = datetime.utcnow()
            
            db.session.commit()
        
        # Números disponibles para cantar
        available_numbers = list(range(1, 76))
        random.shuffle(available_numbers)
        called_numbers = []
        
        # Velocidad del juego (segundos entre números)
        speed = config.velocidad_juego
        
        active_games[room_id] = True
        
        for number in available_numbers:
            if room_id not in active_games:
                break
                
            called_numbers.append(number)
            
            with db.session.begin():
                # Actualizar juego
                game = Game.query.filter_by(room_id=room_id).order_by(Game.id.desc()).first()
                game.set_numeros_cantados(called_numbers)
                
                # Marcar automáticamente en todos los cartones
                cartones = Carton.query.filter_by(room_id=room_id).all()
                winner_found = False
                
                for carton in cartones:
                    marked = auto_mark_numbers(carton, called_numbers)
                    
                    # Verificar bingo
                    if check_bingo(carton.get_numeros(), marked):
                        carton.es_ganador = True
                        game.ganador_id = carton.user_id
                        game.premio_ganador = room.pozo_acumulado
                        
                        # Dar premio al ganador
                        winner = User.query.get(carton.user_id)
                        winner.tokens += int(room.pozo_acumulado)
                        
                        winner_found = True
                        break
                
                db.session.commit()
                
                if winner_found:
                    break
            
            time.sleep(speed)
        
        # Finalizar juego
        with db.session.begin():
            room = Room.query.get(room_id)
            game = Game.query.filter_by(room_id=room_id).order_by(Game.id.desc()).first()
            
            room.estado = 'terminada'
            room.fecha_fin = datetime.utcnow()
            game.estado = 'finalizado'
            game.fecha_fin = datetime.utcnow()
            
            db.session.commit()
        
        # Limpiar juego activo
        if room_id in active_games:
            del active_games[room_id]
            
    except Exception as e:
        print(f"Error en el juego {room_id}: {e}")
        if room_id in active_games:
            del active_games[room_id]

@game_bp.route('/game/<int:room_id>/start', methods=['POST'])
@jwt_required()
def start_game(room_id):
    """Iniciar juego (solo admin o automático)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        room = Room.query.get(room_id)
        
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        # Solo admin puede iniciar manualmente
        if not user.is_admin:
            return jsonify({'error': 'No tienes permisos para iniciar el juego'}), 403
        
        if room.estado != 'abierta' and room.estado != 'llena':
            return jsonify({'error': 'No se puede iniciar el juego en esta sala'}), 400
        
        # Verificar que hay cartones vendidos
        cartones_count = Carton.query.filter_by(room_id=room_id).count()
        if cartones_count == 0:
            return jsonify({'error': 'No hay cartones vendidos'}), 400
        
        # Iniciar juego en hilo separado
        game_thread = threading.Thread(target=run_game, args=(room_id,))
        game_thread.daemon = True
        game_thread.start()
        
        return jsonify({'message': 'Juego iniciado'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@game_bp.route('/game/<int:room_id>/status', methods=['GET'])
@jwt_required()
def get_game_status(room_id):
    """Obtener estado actual del juego"""
    try:
        room = Room.query.get(room_id)
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        game = Game.query.filter_by(room_id=room_id).order_by(Game.id.desc()).first()
        if not game:
            return jsonify({'error': 'Juego no encontrado'}), 404
        
        # Obtener cartones del usuario actual
        user_id = get_jwt_identity()
        user_cartones = Carton.query.filter_by(user_id=user_id, room_id=room_id).all()
        
        response_data = {
            'room': room.to_dict(),
            'game': game.to_dict(),
            'user_cartones': [carton.to_dict() for carton in user_cartones],
            'is_active': room_id in active_games
        }
        
        # Si hay ganador, incluir información
        if game.ganador_id:
            winner = User.query.get(game.ganador_id)
            response_data['winner'] = {
                'id': winner.id,
                'nombre': winner.nombre,
                'apellido': winner.apellido,
                'premio': game.premio_ganador
            }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@game_bp.route('/game/<int:room_id>/auto-start', methods=['POST'])
def auto_start_game(room_id):
    """Iniciar juego automáticamente cuando se cumplen condiciones"""
    try:
        room = Room.query.get(room_id)
        if not room:
            return jsonify({'error': 'Sala no encontrada'}), 404
        
        # Verificar condiciones para inicio automático
        cartones_count = Carton.query.filter_by(room_id=room_id).count()
        
        # Iniciar si hay al menos 2 cartones o si la sala está llena
        should_start = (
            cartones_count >= 2 or 
            room.estado == 'llena' or
            cartones_count >= room.jugadores_maximo * 2  # Promedio de 2 cartones por jugador
        )
        
        if should_start and room.estado in ['abierta', 'llena'] and room_id not in active_games:
            # Iniciar juego en hilo separado
            game_thread = threading.Thread(target=run_game, args=(room_id,))
            game_thread.daemon = True
            game_thread.start()
            
            return jsonify({'message': 'Juego iniciado automáticamente'}), 200
        
        return jsonify({'message': 'Condiciones no cumplidas para inicio automático'}), 200
        
    except Exception as e:
        return jsonify({'error': 'Error interno del servidor'}), 500

@game_bp.route('/game/<int:room_id>/stop', methods=['POST'])
@jwt_required()
def stop_game(room_id):
    """Detener juego (solo admin)"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user.is_admin:
            return jsonify({'error': 'No tienes permisos para detener el juego'}), 403
        
        # Detener juego
        if room_id in active_games:
            del active_games[room_id]
        
        # Actualizar estado en base de datos
        room = Room.query.get(room_id)
        game = Game.query.filter_by(room_id=room_id).order_by(Game.id.desc()).first()
        
        if room:
            room.estado = 'terminada'
            room.fecha_fin = datetime.utcnow()
        
        if game:
            game.estado = 'finalizado'
            game.fecha_fin = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({'message': 'Juego detenido'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

@game_bp.route('/game/<int:room_id>/mark-number', methods=['POST'])
@jwt_required()
def mark_number(room_id):
    """Marcar número en cartón (manual, aunque el auto-marcado está activo)"""
    try:
        user_id = get_jwt_identity()
        data = request.get_json()
        
        carton_id = data.get('carton_id')
        number = data.get('number')
        
        if not carton_id or not number:
            return jsonify({'error': 'carton_id y number son requeridos'}), 400
        
        carton = Carton.query.filter_by(id=carton_id, user_id=user_id, room_id=room_id).first()
        if not carton:
            return jsonify({'error': 'Cartón no encontrado'}), 404
        
        # Verificar que el número está en el cartón
        carton_numbers = carton.get_numeros()
        flat_numbers = []
        for row in carton_numbers:
            flat_numbers.extend(row)
        
        if number not in flat_numbers:
            return jsonify({'error': 'Número no está en el cartón'}), 400
        
        # Marcar número
        marked_numbers = carton.get_numeros_marcados()
        if number not in marked_numbers:
            marked_numbers.append(number)
            carton.set_numeros_marcados(marked_numbers)
            db.session.commit()
        
        return jsonify({
            'message': 'Número marcado',
            'carton': carton.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error interno del servidor'}), 500

