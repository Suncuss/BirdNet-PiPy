import os
import datetime

import wave
import pyaudio
from flask import Flask, request, jsonify

from ..configs import config

app = Flask(__name__)

def record_audio(file_path, recording_length):

    sample_rate = config.SAMPLE_RATE
    buffer_size = 1000

    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, input=True, frames_per_buffer=buffer_size)
    frames = []

    print("Recording started for {} seconds".format(recording_length))
    for _ in range(0, int(sample_rate / buffer_size * recording_length)):
        data = stream.read(buffer_size)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    audio.terminate()

    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(audio.get_sample_size(pyaudio.paInt16))
        wf.setframerate(sample_rate)
        wf.writeframes(b''.join(frames))

@app.route('/start', methods=['POST'])
def start():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    recording_length = config.RECORDING_LENGTH
    recording_path = os.path.join(config.RECODING_DIR, timestamp +'.wav')
    record_audio(recording_path, recording_length)
    return jsonify({"message": "Recording Finished", "path": recording_path, "length": recording_length})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
