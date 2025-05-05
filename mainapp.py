# backend/app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel.db'  # Example SQLite database
db = SQLAlchemy(app)

# --- Data Models ---

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_number = db.Column(db.String(10), unique=True, nullable=False)
    status = db.Column(db.String(20), default='occupied')  # occupied, checked_out, cleaning, clean
    last_cleaned = db.Column(db.DateTime)
    checkouts = db.relationship('Checkout', backref='room', lazy=True)

    def __repr__(self):
        return f"<Room {self.room_number}>"

class Checkout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    scheduled_checkout = db.Column(db.DateTime, nullable=False)
    actual_checkout = db.Column(db.DateTime)
    late_checkout_approved = db.Column(db.Boolean, default=False)
    late_checkout_time = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Checkout for Room {self.room_id} at {self.scheduled_checkout}>"

class Housekeeper(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    assigned_rooms = db.relationship('CleaningTask', backref='housekeeper', lazy=True)

    def __repr__(self):
        return f"<Housekeeper {self.name}>"

class CleaningTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('room.id'), nullable=False)
    housekeeper_id = db.Column(db.Integer, db.ForeignKey('housekeeper.id'), nullable=False)
    status = db.Column(db.String(20), default='pending') # pending, in_progress, completed
    started_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)

    def __repr__(self):
        return f"<Cleaning Task for Room {self.room_id} by {self.housekeeper_id}>"

# --- API Endpoints ---

# Get all rooms and their status
@app.route('/rooms', methods=['GET'])
def get_rooms():
    rooms = Room.query.all()
    output = []
    for room in rooms:
        room_data = {
            'id': room.id,
            'room_number': room.room_number,
            'status': room.status,
            'last_cleaned': room.last_cleaned.isoformat() if room.last_cleaned else None
        }
        output.append(room_data)
    return jsonify({'rooms': output})

# Get a specific room's details
@app.route('/rooms/<int:room_id>', methods=['GET'])
def get_room(room_id):
    room = Room.query.get_or_404(room_id)
    room_data = {
        'id': room.id,
        'room_number': room.room_number,
        'status': room.status,
        'last_cleaned': room.last_cleaned.isoformat() if room.last_cleaned else None,
        'checkouts': [{'scheduled': co.scheduled_checkout.isoformat(), 'actual': co.actual_checkout.isoformat() if co.actual_checkout else None, 'late_approved': co.late_checkout_approved, 'late_time': co.late_checkout_time.isoformat() if co.late_checkout_time else None} for co in room.checkouts]
    }
    return jsonify(room_data)

# Update room status (e.g., checked_out, cleaning, clean)
@app.route('/rooms/<int:room_id>', methods=['PUT'])
def update_room_status(room_id):
    room = Room.query.get_or_404(room_id)
    data = request.get_json()
    if 'status' in data:
        room.status = data['status']
        if room.status == 'clean':
            room.last_cleaned = datetime.utcnow()
        db.session.commit()
        return jsonify({'message': f'Room {room.room_number} status updated to {room.status}'})
    return jsonify({'error': 'Missing status in request'}), 400

# Record a checkout
@app.route('/checkouts', methods=['POST'])
def record_checkout():
    data = request.get_json()
    room_number = data.get('room_number')
    actual_checkout_str = data.get('actual_checkout')

    if not room_number or not actual_checkout_str:
        return jsonify({'error': 'Missing room_number or actual_checkout'}), 400

    room = Room.query.filter_by(room_number=room_number).first()
    if not room:
        return jsonify({'error': f'Room {room_number} not found'}), 404

    checkout = Checkout.query.filter_by(room_id=room.id).order_by(Checkout.scheduled_checkout.desc()).first() # Assuming the latest scheduled checkout is the relevant one
    if checkout:
        checkout.actual_checkout = datetime.fromisoformat(actual_checkout_str)
        room.status = 'checked_out'
        db.session.commit()
        return jsonify({'message': f'Checkout recorded for room {room_number}'})
    else:
        return jsonify({'error': f'No scheduled checkout found for room {room_number}'}), 404

# Request a late checkout
@app.route('/checkouts/<int:checkout_id>/late', methods=['PUT'])
def request_late_checkout(checkout_id):
    checkout = Checkout.query.get_or_404(checkout_id)
    data = request.get_json()
    requested_time_str = data.get('requested_time')

    if not requested_time_str:
        return jsonify({'error': 'Missing requested_time'}), 400

    checkout.late_checkout_time = datetime.fromisoformat(requested_time_str)
    # In a real application, you'd implement logic to check availability and potentially calculate fees
    checkout.late_checkout_approved = False # Initially set to false, to be approved by staff
    db.session.commit()
    return jsonify({'message': f'Late checkout requested for room {checkout.room.room_number} until {checkout.late_checkout_time}'})

# Approve or deny a late checkout request
@app.route('/checkouts/<int:checkout_id>/approve_late', methods=['PUT'])
def approve_late_checkout(checkout_id):
    checkout = Checkout.query.get_or_404(checkout_id)
    data = request.get_json()
    approved = data.get('approved')

    if approved is None:
        return jsonify({'error': 'Missing approval status'}), 400

    checkout.late_checkout_approved = bool(approved)
    # Here you might also update the room status or apply fees
    db.session.commit()
    return jsonify({'message': f'Late checkout for room {checkout.room.room_number} {"approved" if checkout.late_checkout_approved else "denied"}'})

# Get all housekeepers
@app.route('/housekeepers', methods=['GET'])
def get_housekeepers():
    housekeepers = Housekeeper.query.all()
    output = []
    for housekeeper in housekeepers:
        housekeeper_data = {
            'id': housekeeper.id,
            'name': housekeeper.name
        }
        output.append(housekeeper_data)
    return jsonify({'housekeepers': output})

# Assign a cleaning task to a housekeeper
@app.route('/cleaning_tasks', methods=['POST'])
def assign_cleaning_task():
    data = request.get_json()
    room_number = data.get('room_number')
    housekeeper_id = data.get('housekeeper_id')

    if not room_number or not housekeeper_id:
        return jsonify({'error': 'Missing room_number or housekeeper_id'}), 400

    room = Room.query.filter_by(room_number=room_number).first()
    housekeeper = Housekeeper.query.get_or_404(housekeeper_id)

    if not room:
        return jsonify({'error': f'Room {room_number} not found'}), 404

    if room.status != 'checked_out':
        return jsonify({'error': f'Room {room_number} is not checked out yet'}), 400

    new_task = CleaningTask(room_id=room.id, housekeeper_id=housekeeper.id)
    db.session.add(new_task)
    room.status = 'cleaning'
    db.session.commit()
    return jsonify({'message': f'Cleaning task assigned to {housekeeper.name} for room {room_number}'}), 201

# Update the status of a cleaning task
@app.route('/cleaning_tasks/<int:task_id>', methods=['PUT'])
def update_cleaning_task_status(task_id):
    task = CleaningTask.query.get_or_404(task_id)
    data = request.get_json()
    status = data.get('status')

    if not status:
        return jsonify({'error': 'Missing status'}), 400

    task.status = status
    if status == 'in_progress' and not task.started_at:
        task.started_at = datetime.utcnow()
    elif status == 'completed' and not task.completed_at:
        task.completed_at = datetime.utcnow()
        room = Room.query.get(task.room_id)
        if room:
            room.status = 'clean'
            room.last_cleaned = task.completed_at
    db.session.commit()
    return jsonify({'message': f'Cleaning task for room {task.room.room_number} updated to {status}'})

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Example: Add a room if it doesn't exist
        if not Room.query.filter_by(room_number='101').first():
            db.session.add(Room(room_number='101'))
            db.session.commit()
        if not Housekeeper.query.filter_by(name='Alice').first():
            db.session.add(Housekeeper(name='Alice'))
            db.session.commit()
    app.run(debug=True)
