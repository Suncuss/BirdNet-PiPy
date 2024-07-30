from flask import Flask
from flask_socketio import SocketIO
import pyaudio
import numpy as np
import threading
import queue
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, cors_allowed_origins="*")

CHUNK = 2048  # Increased from 1024
FORMAT = pyaudio.paFloat32  # Changed from paInt16
CHANNELS = 1
RATE = 48000  # Increased from 44100

audio_queue = queue.Queue(maxsize=10)
stop_audio_stream = threading.Event()

def audio_stream_producer():
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    try:
        while not stop_audio_stream.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                audio_queue.put(data, block=False)
            except queue.Full:
                continue
            except OSError as e:
                print(f"Error reading from audio stream: {e}")
                time.sleep(0.1)
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

def process_audio(audio_data):
    # Convert to numpy array
    np_data = np.frombuffer(audio_data, dtype=np.float32)
    
    # Normalize audio (adjust volume)
    np_data = np.clip(np_data, -1.0, 1.0)
    
    # Convert back to bytes
    return np_data.tobytes()

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('start_stream')
def start_stream():
    global audio_thread
    stop_audio_stream.clear()
    audio_thread = threading.Thread(target=audio_stream_producer)
    audio_thread.start()
    
    while not stop_audio_stream.is_set():
        try:
            data = audio_queue.get(timeout=1)
            processed_data = process_audio(data)
            socketio.emit('audio_chunk', {'audio': processed_data})
        except queue.Empty:
            continue
        socketio.sleep(0)

@socketio.on('stop_stream')
def stop_stream():
    stop_audio_stream.set()
    if 'audio_thread' in globals():
        audio_thread.join()

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')
    stop_stream()

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5010)