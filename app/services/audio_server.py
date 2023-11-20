import os
import datetime

from flask import Flask, request, jsonify

from ..configs import config
from ..tools import utils

app = Flask(__name__)

@app.route('/record_audio', methods=['POST'])
def record_audio():
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    recording_length = config.RECORDING_LENGTH
    recording_path = os.path.join(config.RECODING_DIR, timestamp +'.wav')
    print(f"Recording audio for {recording_length} seconds at {recording_path}")
    utils.record_audio(recording_path, recording_length)
    return jsonify({"message": "Recording Finished", "path": recording_path, "length": recording_length})

@app.route('/trim_audio', methods=['POST'])
def trim_audio():
    audio_file_path = request.json.get('audio_file_path')
    start_time = request.json.get('start_time')
    end_time = request.json.get('end_time')
    start_time, end_time = utils.calulate_padded_start_and_end(start_time, end_time, config.RECORDING_LENGTH)
    print(f"Trimming audio from {start_time} to {end_time}")
    trimmed_audio_file_path = request.json.get('trimmed_audio_file_path')
    utils.trim_audio(audio_file_path, trimmed_audio_file_path, start_time, end_time)

    return jsonify({"message": "Audio Trimmed", "path": trimmed_audio_file_path})

@app.route('/generate_spectrogram', methods=['POST'])
def create_spectrogram():
    audio_file_path = request.json.get('audio_file_path')
    spectrogram_file_path = request.json.get('spectrogram_file_path')
    graph_title = request.json.get('graph_title')
    print(f"Generating spectrogram for {audio_file_path} at {spectrogram_file_path}")
    utils.generate_spectrogram(audio_file_path, spectrogram_file_path, graph_title)

    return jsonify({"message": "Spectrogram Created", "path": spectrogram_file_path})

if __name__ == '__main__':
    app.run(debug=True, port=5000)
