import datetime

import numpy as np
from flask import Flask, request, jsonify

from ..configs import config
from ..tools.model_loader import ModelLoader
from ..tools import utils

app = Flask(__name__)

# Load the model at startup

model_config = {
    "model_path": config.MODEL_PATH,
    "meta_model_path": config.META_MODEL_PATH,
    "labels_path": config.LABELS_PATH
}

model_loader = ModelLoader(**model_config)
model = model_loader.load_model()
meta_model = model_loader.load_meta_model()
labels = model_loader.load_labels()

def generate_local_species_list(lat, lon, week, meta_model,labels):
    # Generate local species list
    local_species = []
    sf_thresh = 0.03

    meta_model_input = np.expand_dims(np.array([lat, lon, week], dtype='float32'), 0)
    meta_model.set_tensor(model_loader.meta_input_layer_index, meta_model_input)

    meta_model.invoke()

    meta_model_output = meta_model.get_tensor(model_loader.meta_output_layer_index)[0]
    meta_model_output = np.where(meta_model_output >= sf_thresh, meta_model_output, 0)
    meta_model_output = list(zip(meta_model_output, labels))
    meta_model_output = sorted(meta_model_output, key=lambda x: x[0], reverse=True)

    for species in meta_model_output:
        if species[0] >= float(sf_thresh):
            local_species.append(species[1])

    return local_species

def analyze_audio(model, audio_input, labels, sensitivity, cutoff):

    model_input = np.array(np.expand_dims(audio_input, 0), dtype='float32')
    model.set_tensor(model_loader.input_layer_index, model_input)
    model.invoke()
    model_output = model.get_tensor(model_loader.output_layer_index)[0]
    
    def custom_sigmoid(x, sensitivity):
        return 1 / (1.0 + np.exp(-sensitivity * x))
    
    model_output = custom_sigmoid(model_output, sensitivity)
    model_output = np.where(model_output >= cutoff, model_output, 0)
    model_output = dict(zip(labels, model_output))
    model_output = {k: v for k, v in model_output.items() if v != 0}
    model_output = sorted(model_output.items(), key=lambda x: x[1], reverse=True)

    # Check for the prescence of Human
    human_detection = any('Human' in x[0] for x in model_output)
    if human_detection:
        print("Human Detected")
        return []
    return model_output

def predict(model, meta_model, audio_file_path, labels, lat, lon, week, sensitivity, cutoff):
    
    chunk_length = config.RECORDING_CHUNK_LENGTH
    sample_rate = config.SAMPLE_RATE

    local_species_list = generate_local_species_list(lat, lon, week, meta_model, labels)
    audio_chunks = utils.split_audio(audio_file_path, chunk_length, sample_rate)
    results = []

    for audio_chunk, chuck_index in zip(audio_chunks, range(len(audio_chunks))):
        species_in_audio_chunk = analyze_audio(model, audio_chunk, labels, sensitivity, cutoff)
        filtered_species_list = [x for x in species_in_audio_chunk if x[0] in local_species_list]

        # construct result
        source_file_name = audio_file_path.split('/')[-1]
        file_timestamp_str = source_file_name.split('.')[0]
        file_timestamp = datetime.datetime.strptime(file_timestamp_str, "%Y%m%d_%H%M%S")
        start_timestamp = file_timestamp  + datetime.timedelta(seconds=chuck_index * chunk_length)
        start_date_str = start_timestamp.strftime("%Y-%m-%d")
        start_time_str = start_timestamp.strftime("%H:%M:%S")


        for species in filtered_species_list:
            sci_name = species[0].split('_')[0]
            com_name = species[0].split('_')[1]
            confidence = float(species[1])            
            birg_song_file_name = (
                f"{com_name.replace(' ', '_')}_{round(confidence * 100)}_"
                f"{start_date_str}-birdnet-{start_time_str}{config.BIRD_SONG_FORMAT}"
            )
            
            results.append({
                "Date": start_date_str,
                "Time": start_time_str,
                "Sci_Name": sci_name,
                "Com_Name": com_name,
                "Confidence": confidence,
                "Lat": lat,
                "Lon": lon,
                "Cutoff": cutoff,
                "Week": week,
                "Sens": sensitivity,
                "Bird_Song_File_Name": birg_song_file_name,
                "Bird_Song_Duration": chunk_length,
                "Source_File_Name": source_file_name,
                "Chunk_Index": chuck_index
            })

    return results

@app.route('/analyze', methods=['POST'])

def analyze():
    data = request.json
    # Extract parameters from data
    audio_file_path = data.get('audio_file_path')

    # Set other metadata parameters
    lat = config.LAT
    lon = config.LON
    week = utils.get_week_of_year()
    cutoff = config.CUTOFF
    sensitivity = config.SENSITIVITY
    results = predict(model, meta_model, audio_file_path, labels, lat, lon, week, sensitivity, cutoff)
    print("Finished analyzing file: {}, total detections: {}".format(audio_file_path, len(results)))

    return jsonify(results)
    
if __name__ == '__main__':
    app.run(debug=True, port=5002)
