from flask import Flask, render_template
from flask_socketio import SocketIO, emit
import time
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

# Simulated bird detection function
def detect_birds():
    birds = ['American Robin', 'Blue Jay', 'Northern Cardinal', 'Song Sparrow', 'Black-capped Chickadee']
    return {
        'id': int(time.time() * 1000),
        'species': random.choice(birds),
        'timestamp': time.time() * 1000,
        'confidence': round(random.uniform(0.7, 1.0), 2)
    }

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('start_detection')
def handle_start_detection():
    while True:
        detection = detect_birds()
        emit('bird_detected', detection)
        socketio.sleep(5)  # Simulate detection every 5 seconds

if __name__ == '__main__':
    socketio.run(app, debug=True, port=5008)