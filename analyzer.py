from flask import Flask, request, jsonify
import numpy as np
from model_loader import ModelLoader
from audio_processor import split_audio
import datetime


app = Flask(__name__)

# Load the model at startup
model_config = {
    "model_name": "BirdNET_GLOBAL_6K_V2.4_Model_FP16",
    "meta_model_name": "BirdNET_GLOBAL_6K_V2.4_MData_Model_FP16",
    "model_dir": "models"
}

model_loader = ModelLoader(**model_config)
model = model_loader.load_model()
meta_model = model_loader.load_meta_model()
labels = model_loader.load_labels()

def generate_local_species_list(lat, lon, week, meta_model,labels):
    # For testing LAT 36.0181 LON -78.9697 WEEK 46
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

def predict(model, audio_input, labels, sensitivity=0.75, cutoff=0.7):

    model_input = np.array(np.expand_dims(audio_input, 0), dtype='float32')
    model.set_tensor(model_loader.input_layer_index, model_input)
    model.invoke()
    model_output = model.get_tensor(model_loader.output_layer_index)[0]

    def custom_sigmoid(x, sensitivity=1.0):
        return 1 / (1.0 + np.exp(-sensitivity * x))
    
    model_output = custom_sigmoid(model_output, sensitivity)
    model_output = np.where(model_output >= cutoff, model_output, 0)
    model_output = dict(zip(labels, model_output))
    model_output = {k: v for k, v in model_output.items() if v != 0}
    model_output = sorted(model_output.items(), key=lambda x: x[1], reverse=True)

    # Check for the prescence of Human
    human_detection = any('Human' in x[0] for x in model_output)
    if human_detection:
        return []
    return model_output

def package_results(predictions, local_species, meta_data):
    # Unpack file_name, chunk_index, chunk_duration, lat, lon, week from meta_data
    file_name = meta_data["file_name"]
    chunk_index = meta_data["chunk_index"]
    chunk_duration = meta_data["chunk_duration"]
    lat = meta_data["lat"]
    lon = meta_data["lon"]
    week = meta_data["week"]

    # Intersect prediction with local species list
    predictions = [x for x in predictions if x[0] in local_species]

    # Generate start_time and date
    file_timestamp_str = file_name.split('.')[0]
    file_timestamp = datetime.datetime.strptime(file_timestamp_str, "%Y%m%d_%H%M%S")
    start_timestamp = file_timestamp  + datetime.timedelta(seconds=chunk_index * chunk_duration)
    start_date_str = start_timestamp.strftime("%Y-%m-%d")
    start_time_str = start_timestamp.strftime("%H:%M:%S")

    results = []

    for prediction in predictions:
        results.append({
            "sci_name": prediction[0].split('_')[0],
            "com_name": prediction[0].split('_')[1],
            "probability": prediction[1],
            "file_name": file_name,
            "start_date": start_date_str,
            "start_time": start_time_str,
            "lat": lat,
            "lon": lon,
            "week": week
        })

    return results

meta_data_example = {
    "file_name": "20231115_111713.wav",
    "chunk_index": 2,
    "chunk_duration": 3,
    "lat": 36.0181,
    "lon": -78.9697,
    "week": 43
}

json_argument = {"audio_file_name": "20231115_111713.wav", "lat": 36.0181, "lon": -78.9697, "week": 43}

@app.route('/analyze', methods=['POST'])

def analyze_audio():
    data = request.json
    # Extract parameters from data
    lat = data.get('lat')
    lon = data.get('lon')
    week = data.get('week')
    audio_file_name = data.get('audio_file_name')

    local_species = generate_local_species_list(lat, lon, week, meta_model, labels)
    audio_chunks = split_audio(audio_file_name, 3)

    for audio_chunk, chuck_index in zip(audio_chunks, range(len(audio_chunks))):
        predictions = predict(model, audio_chunk, labels)
       
        meta_data = {
            "file_name": audio_file_name,
            "chunk_index": chuck_index,
            "chunk_duration": 3,
            "lat": lat,
            "lon": lon,
            "week": week
        }
        results = package_results(predictions, local_species, meta_data)
        print(results)

    return jsonify({"Message": "Analysis Complete"})

    
if __name__ == '__main__':
    app.run(debug=True, port=5005)
