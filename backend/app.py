# backend/app.py
from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from models import db, Room, Checkout, Housekeeper, CleaningTask  # Import the models

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hotel.db'  # Example SQLite database (for development)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # To suppress a warning
db.init_app(app)  # Initialize SQLAlchemy with the app

# --- Helper Functions ---

def get_room_data(room):
    """Helper function to format room data for API responses."""
    return {
        'id': room.id,
        'room_number': room.room_number,
        'status': room.status,
        'last_cleaned': room.last_cleaned.isoformat() if room.last_cleaned else None,
        'checkouts': [get_checkout_data(co) for co in room.checkouts],
        'cleaning_tasks': [get_cleaning_task_data(ct) for ct in room.cleaning_tasks] #Added
    }

def get_checkout_data(checkout):
    """Helper function to format checkout data."""
    return {
        'id': checkout.id,
        'scheduled_checkout': checkout.scheduled_checkout.isoformat(),
        'actual_checkout': checkout.actual_checkout.isoformat() if checkout.actual_checkout else None,
        'late_checkout_approved': checkout.late_checkout_approved,
        'late_checkout_time': checkout.late_checkout_time.isoformat() if checkout.late_checkout_time else None,
    }

def get_housekeeper_data(housekeeper):
    """Helper function to format housekeeper data."""
    return {
        'id': housekeeper.id,
        'name': housekeeper.name,
    }

def get_cleaning_task_data(cleaning_task):
    """Helper function to format cleaning task data."""
    return {
        'id': cleaning_task.id,
        'room_id': cleaning_task.room_id,
        'housekeeper_id': cleaning_task.housekeeper_id,
        'status': cleaning_task.status,
        'started_at': cleaning_task.started_at.isoformat() if cleaning_task.started_at else None,
        'completed_at': cleaning_task.completed_at.isoformat() if cleaning_task.completed_at else None,
    }

# --- API Endpoints ---

# Get all rooms and their status
@app.route('/rooms', methods=['GET'])
def get_rooms():
    rooms = Room.query.all()
    output = [get_room_data(room) for room in rooms]
    return jsonify({'rooms': output})

# Get a specific room's details
@app.route('/rooms/<int:room_id>', methods=['GET'])
def get_room(room_id):
    room = Room.query.get_or_404(room_id)
    return jsonify(get_room_data(room))

# Update room status (e.g., checked_out, cleaning, clean)
@app.route('/rooms/<int:room_id>', methods=['PUT'])
def update_room_status(room_id):
    room = Room.query.get_or_404(room_id)
    data = request.get_json()
    if 'status' not in data:
        return jsonify({'error': 'Missing status in request'}), 400

    new_status = data['status']
    allowed_statuses = ['occupied', 'checked_out', 'cleaning', 'clean'] #Added
    if new_status not in allowed_statuses:
        return jsonify({'error': f'Invalid status: {new_status}'}), 400

    room.status = new_status
    if room.status == 'clean':
        room.last_cleaned = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': f'Room {room.room_number} status updated to {room.status}'})

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

    checkout = Checkout.query.filter_by(room_id=room.id).order_by(Checkout.scheduled_checkout.desc()).first()  # Assuming the latest scheduled checkout is the relevant one
    if not checkout:
        return jsonify({'error': f'No scheduled checkout found for room {room_number}'}), 404

    try:
        actual_checkout = datetime.fromisoformat(actual_checkout_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format for actual_checkout.  Use ISO format (e.g., 2024-08-01T10:00:00)'}), 400

    checkout.actual_checkout = actual_checkout
    room.status = 'checked_out'
    db.session.commit()
    return jsonify({'message': f'Checkout recorded for room {room_number}'})

# Request a late checkout
@app.route('/checkouts/<int:checkout_id>/late', methods=['PUT'])
def request_late_checkout(checkout_id):
    checkout = Checkout.query.get_or_404(checkout_id)
    data = request.get_json()
    requested_time_str = data.get('requested_time')

    if not requested_time_str:
        return jsonify({'error': 'Missing requested_time'}), 400

    try:
        requested_time = datetime.fromisoformat(requested_time_str)
    except ValueError:
        return jsonify({'error': 'Invalid date format for requested_time.  Use ISO format (e.g., 2024-08-01T11:00:00)'}), 400

    if requested_time <= checkout.scheduled_checkout:
        return jsonify({'error': 'requested_time must be after the scheduled checkout'}), 400


    checkout.late_checkout_time = requested_time
    # In a real application, you'd implement logic to check availability and potentially calculate fees
    checkout.late_checkout_approved = False  # Initially set to false, to be approved by staff
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
    db.session.commit()
    return jsonify({'message': f'Late checkout for room {checkout.room.room_number} {"approved" if checkout.late_checkout_approved else "denied"}'})

# Get all housekeepers
@app.route('/housekeepers', methods=['GET'])
def get_housekeepers():
    housekeepers = Housekeeper.query.all()
    output = [get_housekeeper_data(housekeeper) for housekeeper in housekeepers]
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
        return jsonify({'error': f'Room {room_number} is not checked out yet.  Current status: {room.status}'}), 400

    # Check if there's already a pending or in progress task for this room
    existing_task = CleaningTask.query.filter(
        CleaningTask.room_id == room.id,
        CleaningTask.status.in_(['pending', 'in_progress'])
    ).first()
    if existing_task:
        return jsonify({'error': f'Room {room_number} already has a cleaning task in progress or pending'}), 409


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

    allowed_statuses = ['pending', 'in_progress', 'completed'] #Added
    if status not in allowed_statuses:
        return jsonify({'error': f'Invalid status: {status}'}), 400
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

# Get all cleaning tasks
@app.route('/cleaning_tasks', methods=['GET'])
def get_cleaning_tasks():
    tasks = CleaningTask.query.all()
    output = [get_cleaning_task_data(task) for task in tasks]
    return jsonify({'cleaning_tasks': output})

# Delete a cleaning task
@app.route('/cleaning_tasks/<int:task_id>', methods=['DELETE'])
def delete_cleaning_task(task_id):
    task = CleaningTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'message': f'Cleaning task {task_id} deleted'})

# --- Database Initialization ---

@app.before_first_request
def create_tables():
    """Create database tables before the first request."""
    with app.app_context():
        db.create_all()
        #Check if there are rooms, if not add default
        if not Room.query.first():
            for i in range(1, 11):  # Create 10 rooms for example
                room = Room(room_number=f"10{i}")
                db.session.add(room)
            db.session.commit()
        if not Housekeeper.query.first():
            h1 = Housekeeper(name="Alice")
            h2 = Housekeeper(name="Bob")
            db.session.add(h1)
            db.session.add(h2)
            db.session.commit()

# --- Main ---
if __name__ == '__main__':
    app.run(debug=True)
