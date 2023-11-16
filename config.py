DEBUG_MODE = True

# Root path
ROOT_PATH = "."

# Database configuration
DATABASE_PATH = 'db/birds.db'

# Model configuration

MODEL_PATH = 'models/BirdNET_GLOBAL_6K_V2.4_Model_FP16.tflite'
META_MODEL_PATH = 'models/BirdNET_GLOBAL_6K_V2.4_MData_Model_FP16.tflite'
LABELS_PATH = 'models/labels.txt'

# Audio configuration
AUDIO_DIR = 'audio_files/'
CHUNK_LENGTH = 3  # Length of audio chunks in seconds
SAMPLE_RATE = 48000  # Sample rate of audio files



LOG_FILE_PATH = 'logs/birdnet.log'
LOGGING_LEVEL = 'INFO'  # Set the logging level to INFO to see BirdNET's output


# Geolocation configuration
LAT = 36.018
LON = -78.969

# Prediction configuration
SENSITIVITY = 0.75
CUTOFF = 0.7


# Job dispatcher configuration
INCOMING_DIR = "audio_files"
PROCESSED_DIR = "processed_audio_files"

