from flask import Flask, request
import numpy as np
from model_loader import ModelLoader
from audio_processor import split_audio


app = Flask(__name__)

# Load the model at startup
model_config = {
    "model_name": "model",
    "meta_model_name": "meta_model",
    "model_dir": "path/to/your/model/directory"
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

def predict(model, chunks, labels, sensitivity=1):
    # Predict
    predictions = {}
    for chunk in chunks:
        model_input = np.array(np.expand_dims(chunk, 0), dtype='float32')
        model.set_tensor(model_loader.input_layer_index, model_input)
        model.invoke()
        model_output = model.get_tensor(model_loader.output_layer_index)[0]

        def custom_sigmoid(x, sensitivity=1.0):
            return 1 / (1.0 + np.exp(-sensitivity * x))
        
        model_output = custom_sigmoid(model_output, sensitivity)
        model_output = dict(zip(labels, model_output))
        model_output = sorted(model_output.items(), key=lambda x: x[1], reverse=True)
        
        # TODO DEAL with human detection
        # Figure out the key for the dict, should be something akin to timestamp


    return predictions


@app.route('/analyze', methods=['POST'])

def analyze_audio():
    data = request.json
    # Extract parameters from data
    lat = data.get('lat')
    lon = data.get('lon')
    week = data.get('week')

    local_species = generate_local_species_list(lat, lon, week, meta_model, labels)


    

