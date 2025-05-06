# backend/models.py (Recommended to separate models into their own file)
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()  # Initialize SQLAlchemy outside of the app context

# --- Data Models ---

class Room(db.Model):
    __tablename__ = 'rooms'  # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='occupied')  # occupied, checked_out, cleaning, clean
    last_cleaned = db.Column(db.DateTime)
    checkouts = db.relationship('Checkout', backref='room', lazy=True)
    cleaning_tasks = db.relationship('CleaningTask', backref='room', lazy=True) # Added relationship

    def __repr__(self):
        return f"<Room {self.room_number}>"

class Checkout(db.Model):
    __tablename__ = 'checkouts' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    scheduled_checkout = db.Column(db.DateTime, nullable=False)
    actual_checkout = db.Column(db.DateTime)
    late_checkout_approved = db.Column(db.Boolean, default=False)
    late_checkout_time = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Checkout for Room {self.room_id} at {self.scheduled_checkout}>"

class Housekeeper(db.Model):
    __tablename__ = 'housekeepers' # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    assigned_rooms = db.relationship('CleaningTask', backref='housekeeper', lazy=True)

    def __repr__(self):
        return f"<Housekeeper {self.name}>"

class CleaningTask(db.Model):
    __tablename__ = 'cleaning_tasks'  # Explicit table name
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('rooms.id'), nullable=False)
    housekeeper_id = db.Column(db.Integer, db.ForeignKey('housekeepers.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Cleaning Task for Room {self.room_id} by {self.housekeeper_id}>"
