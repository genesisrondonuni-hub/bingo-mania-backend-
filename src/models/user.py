from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(50), nullable=False)
    apellido = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    telefono = db.Column(db.String(20))
    avatar = db.Column(db.String(200), default='default-avatar.png')
    tokens = db.Column(db.Integer, default=0)
    tema = db.Column(db.String(20), default='oscuro')
    is_admin = db.Column(db.Boolean, default=False)
    google_id = db.Column(db.String(100))
    datos_bancarios = db.Column(db.Text)  # JSON string
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relaciones
    cartones = db.relationship('Carton', backref='usuario', lazy=True)
    solicitudes_retiro = db.relationship('SolicitudRetiro', backref='usuario', lazy=True)
    
    def set_password(self, password):
        """Establece la contraseña hasheada"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verifica la contraseña"""
        return check_password_hash(self.password_hash, password)
    
    def set_datos_bancarios(self, datos):
        """Establece los datos bancarios como JSON"""
        self.datos_bancarios = json.dumps(datos)
    
    def get_datos_bancarios(self):
        """Obtiene los datos bancarios desde JSON"""
        if self.datos_bancarios:
            return json.loads(self.datos_bancarios)
        return None
    
    def to_dict(self):
        """Convierte el usuario a diccionario"""
        return {
            'id': self.id,
            'nombre': self.nombre,
            'apellido': self.apellido,
            'email': self.email,
            'telefono': self.telefono,
            'avatar': self.avatar,
            'tokens': self.tokens,
            'tema': self.tema,
            'is_admin': self.is_admin,
            'datos_bancarios': self.get_datos_bancarios(),
            'fecha_registro': self.fecha_registro.isoformat() if self.fecha_registro else None
        }
    
    def __repr__(self):
        return f'<User {self.email}>'


class Room(db.Model):
    __tablename__ = 'rooms'
    
    id = db.Column(db.Integer, primary_key=True)
    numero_sala = db.Column(db.Integer, unique=True, nullable=False)
    estado = db.Column(db.String(20), default='abierta')  # abierta, llena, en_juego, terminada
    jugadores_actuales = db.Column(db.Integer, default=0)
    jugadores_maximo = db.Column(db.Integer, default=50)
    pozo_acumulado = db.Column(db.Float, default=0.0)
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)
    
    # Relaciones
    juegos = db.relationship('Game', backref='sala', lazy=True)
    cartones = db.relationship('Carton', backref='sala', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'numero_sala': self.numero_sala,
            'estado': self.estado,
            'jugadores_actuales': self.jugadores_actuales,
            'jugadores_maximo': self.jugadores_maximo,
            'pozo_acumulado': self.pozo_acumulado,
            'fecha_creacion': self.fecha_creacion.isoformat() if self.fecha_creacion else None,
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_fin': self.fecha_fin.isoformat() if self.fecha_fin else None
        }
    
    def __repr__(self):
        return f'<Room {self.numero_sala}>'


class Game(db.Model):
    __tablename__ = 'games'
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    numeros_cantados = db.Column(db.Text)  # JSON string
    cartones_vendidos = db.Column(db.Integer, default=0)
    ganador_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    premio_ganador = db.Column(db.Float)
    estado = db.Column(db.String(20), default='esperando')  # esperando, en_progreso, finalizado
    fecha_inicio = db.Column(db.DateTime)
    fecha_fin = db.Column(db.DateTime)
    
    # Relaciones
    ganador = db.relationship('User', backref='juegos_ganados')
    
    def set_numeros_cantados(self, numeros):
        """Establece los números cantados como JSON"""
        self.numeros_cantados = json.dumps(numeros)
    
    def get_numeros_cantados(self):
        """Obtiene los números cantados desde JSON"""
        if self.numeros_cantados:
            return json.loads(self.numeros_cantados)
        return []
    
    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'numeros_cantados': self.get_numeros_cantados(),
            'cartones_vendidos': self.cartones_vendidos,
            'ganador_id': self.ganador_id,
            'premio_ganador': self.premio_ganador,
            'estado': self.estado,
            'fecha_inicio': self.fecha_inicio.isoformat() if self.fecha_inicio else None,
            'fecha_fin': self.fecha_fin.isoformat() if self.fecha_fin else None
        }
    
    def __repr__(self):
        return f'<Game {self.id} - Room {self.room_id}>'


class Carton(db.Model):
    __tablename__ = 'cartones'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    numeros = db.Column(db.Text, nullable=False)  # JSON string con los números del cartón
    numeros_marcados = db.Column(db.Text)  # JSON string con los números marcados
    es_ganador = db.Column(db.Boolean, default=False)
    fecha_compra = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_numeros(self, numeros):
        """Establece los números del cartón como JSON"""
        self.numeros = json.dumps(numeros)
    
    def get_numeros(self):
        """Obtiene los números del cartón desde JSON"""
        if self.numeros:
            return json.loads(self.numeros)
        return []
    
    def set_numeros_marcados(self, numeros):
        """Establece los números marcados como JSON"""
        self.numeros_marcados = json.dumps(numeros)
    
    def get_numeros_marcados(self):
        """Obtiene los números marcados desde JSON"""
        if self.numeros_marcados:
            return json.loads(self.numeros_marcados)
        return []
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'room_id': self.room_id,
            'numeros': self.get_numeros(),
            'numeros_marcados': self.get_numeros_marcados(),
            'es_ganador': self.es_ganador,
            'fecha_compra': self.fecha_compra.isoformat() if self.fecha_compra else None
        }
    
    def __repr__(self):
        return f'<Carton {self.id} - User {self.user_id}>'


class Config(db.Model):
    __tablename__ = 'config'
    
    id = db.Column(db.Integer, primary_key=True)
    token_bs = db.Column(db.Float, default=1.0)
    token_dolares = db.Column(db.Float, default=0.1)
    costo_carton = db.Column(db.Integer, default=5)
    porcentaje_premio = db.Column(db.Integer, default=70)
    velocidad_juego = db.Column(db.Integer, default=3)
    fecha_actualizacion = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'token_bs': self.token_bs,
            'token_dolares': self.token_dolares,
            'costo_carton': self.costo_carton,
            'porcentaje_premio': self.porcentaje_premio,
            'velocidad_juego': self.velocidad_juego,
            'fecha_actualizacion': self.fecha_actualizacion.isoformat() if self.fecha_actualizacion else None
        }
    
    def __repr__(self):
        return f'<Config {self.id}>'


class SolicitudRetiro(db.Model):
    __tablename__ = 'solicitudes_retiro'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    tokens = db.Column(db.Integer, nullable=False)
    monto_bs = db.Column(db.Float, nullable=False)
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aprobado, rechazado
    fecha_solicitud = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_procesamiento = db.Column(db.DateTime)
    notas_admin = db.Column(db.Text)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'usuario': self.usuario.to_dict() if self.usuario else None,
            'tokens': self.tokens,
            'monto_bs': self.monto_bs,
            'estado': self.estado,
            'fecha_solicitud': self.fecha_solicitud.isoformat() if self.fecha_solicitud else None,
            'fecha_procesamiento': self.fecha_procesamiento.isoformat() if self.fecha_procesamiento else None,
            'notas_admin': self.notas_admin
        }
    
    def __repr__(self):
        return f'<SolicitudRetiro {self.id} - User {self.user_id}>'

