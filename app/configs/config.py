import os
# Base path

BASE_DIR = os.path.expanduser("~/dev/birdnet-pipy")

# Model configuration
MODEL_PATH = f'{BASE_DIR}/app/models/BirdNET_GLOBAL_6K_V2.4_Model_FP16.tflite'
META_MODEL_PATH = f'{BASE_DIR}/app/models/BirdNET_GLOBAL_6K_V2.4_MData_Model_FP16.tflite'
LABELS_PATH = f'{BASE_DIR}/app/models/labels.txt'

# Audio configuration
RECODING_DIR = f'{BASE_DIR}/data/recordings'
RECORDING_LENGTH = 9  # Total length of audio files in seconds
SAMPLE_RATE = 48000  # Sample rate of audio files
RECORDING_CHUNK_LENGTH = 3  # Length of audio chunks in seconds

# Audio extraction and spectrogram configuration
EXTRACTED_AUDIO_DIR = f'{BASE_DIR}/data/extracted_songs'
SPECTROGRAM_DIR = f'{BASE_DIR}/data/extracted_songs_spectrograms'

# Job dispatcher configuration
INCOMING_DIR = f'{BASE_DIR}/data/recordings'
PROCESSED_DIR = f'{BASE_DIR}/data/processed_recordings'
PROCESS_LOG_DIR = f'{BASE_DIR}/data/logs'

# Microservice endpoints
RECORD_ENDPOINT = "http://localhost:5000/record_audio"
AUDIO_TRIMING_ENDPOINT = "http://localhost:5000/trim_audio"
SPECTROGRAM_GENERATION_ENDPOINT = "http://localhost:5000/generate_spectrogram"

GET_TASK_ENDPOINT = "http://localhost:5001/get_task"
COMPLETE_TASK_ENDPOINT = "http://localhost:5001/complete_task"

ANALYZE_ENDPOINT = "http://localhost:5002/analyze"

DB_INSERT_ENDPOINT = "http://localhost:5003/db_insert"
DB_READ_ALL_ENDPOINT = "http://localhost:5003/db_read_all"
DB_READ_ENDPOINT = "http://localhost:5003/db_read_record_with_id"
DB_DELETE_ENDPOINT = "http://localhost:5003/delete"
LOGGING_ENDPOINT = "http://localhost:5003/write_log_to_file"


# BIRDSONG CONFIG
BIRD_SONG_FORMAT = '.wav'

# Spectrogram configuration
SPECTROGRAM_MAX_FREQ_IN_KHZ = 22
SPECTROGRAM_MIN_FREQ_IN_KHZ = 0
SPECTROGRAM_MAX_DBFS = 0
SPECTROGRAM_MIN_DBFS = -200

# Geolocation configuration
LAT = 36.018
LON = -78.969

# Prediction configuration
SENSITIVITY = 0.75
CUTOFF = 0.60

# Database configuration
DATABASE_PATH = f'{BASE_DIR}/data/db/birds.db'
DATABASE_SCHEMA = """
DROP TABLE IF EXISTS detections;
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    Date DATE,
    Time TIME,
    Sci_Name VARCHAR(100) NOT NULL,
    Com_Name VARCHAR(100) NOT NULL,
    Confidence FLOAT,
    Lat FLOAT,
    Lon FLOAT,
    Cutoff FLOAT,
    Sens FLOAT,
    Week INT,
    Bird_Song_File_Name VARCHAR(100) NOT NULL

);
CREATE INDEX detections_Com_Name ON detections (Com_Name);
CREATE INDEX detections_Date_Time ON detections (Date DESC, Time DESC);
"""

# Logging configuration
LOGGING_DIR = f'{BASE_DIR}/data/logs'
LOGGING_LEVEL = 'INFO'  # Set the logging level to INFO to see BirdNET's output