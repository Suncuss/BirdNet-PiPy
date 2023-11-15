import pyaudio
import wave
import threading
import datetime
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
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    recording_length = 9
    recording_path = timestamp +'.wav'
    record_audio(recording_path, recording_length)
    return jsonify({"message": "Recording Finished", "path": recording_path, "length": recording_length})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
