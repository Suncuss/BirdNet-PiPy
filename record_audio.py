import pyaudio
import wave
import threading
import time
from flask import Flask, request, jsonify

app = Flask(__name__)

def record_audio(filename, recording_length):
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=1024)
    frames = []

    print("Recording started for {} seconds".format(recording_length))
    for _ in range(0, int(44100 / 1024 * recording_length)):
        data = stream.read(1024)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(44100)
        wf.writeframes(b''.join(frames))

@app.route('/start', methods=['POST'])
def start():
    data = request.json
    recording_length = data.get('recording_length', 15)  # Default length 10 seconds
    recording_path = data.get('recording_path', 'recording.wav')  # Default path
    # I might need to change it to blocking, so that i can just to it into a infinite loop and not to worry about sleep
    threading.Thread(target=record_audio, args=(recording_path, recording_length)).start()
    return jsonify({"message": "Recording started", "path": recording_path, "length": recording_length})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
