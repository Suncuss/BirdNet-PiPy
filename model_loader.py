import tflite_runtime.interpreter as tflite
import os

class ModelLoader:
    def __init__(self, model_name, meta_model_name, model_dir):
        self.model_name = model_name
        self.meta_model_name = meta_model_name
        self.model_dir = model_dir

        self.model = None
        self.meta_model = None
        
        self.input_layer_index = None
        self.output_layer_index = None
        self.meta_input_layer_index = None
        self.meta_output_layer_index = None

        self.labels = None

    def load_model(self):
        if self.model is None:
            model_path = os.path.join(self.model_dir, self.model_name + '.tflite')
            self.model = tflite.Interpreter(model_path=model_path, num_threads=2)
            self.model.allocate_tensors()
            self.input_layer_index = self.model.get_input_details()[0]['index']
            self.output_layer_index = self.model.get_output_details()[0]['index']
        return self.model

    def load_meta_model(self):
        if self.meta_model is None:
            meta_model_path = os.path.join(self.model_dir, self.meta_model_name + '.tflite')
            self.meta_model = tflite.Interpreter(model_path=meta_model_path)
            self.meta_model.allocate_tensors()
            self.meta_input_layer_index = self.meta_model.get_input_details()[0]['index']
            self.meta_output_layer_index = self.meta_model.get_output_details()[0]['index']
        return self.meta_model

    def load_lables(self):
        label_path = os.path.join(self.model_dir, 'labels.txt')
        with open(label_path, 'r') as f:
            self.labels = [line.strip() for line in f.readlines()]
        return self.labels