DEBUG_MODE = True

# Root path
ROOT_DIR = "./"

# Database configuration
DATABASE_PATH = ROOT_DIR + 'db/birds.db'

# Model configuration

MODEL_PATH = ROOT_DIR + 'models/BirdNET_GLOBAL_6K_V2.4_Model_FP16.tflite'
META_MODEL_PATH = ROOT_DIR + 'models/BirdNET_GLOBAL_6K_V2.4_MData_Model_FP16.tflite'
LABELS_PATH = ROOT_DIR + 'models/labels.txt'

# Audio configuration
RECODING_DIR = ROOT_DIR + 'audio_files/'
RECORDING_LENGTH = 9  # Total length of audio files in seconds
SAMPLE_RATE = 48000  # Sample rate of audio files
RECORDING_CHUNK_LENGTH = 3  # Length of audio chunks in seconds

LOG_FILE_PATH = ROOT_DIR + 'logs/birdnet.log'
LOGGING_LEVEL = 'INFO'  # Set the logging level to INFO to see BirdNET's output

# Geolocation configuration
LAT = 36.018
LON = -78.969

# Prediction configuration
SENSITIVITY = 0.75
CUTOFF = 0.60

# Job dispatcher configuration
INCOMING_DIR = ROOT_DIR + "audio_files/"
PROCESSED_DIR = ROOT_DIR + "processed_audio_files/"
PROCESS_LOG_DIR = ROOT_DIR + "file_processing_log/"

# Microservice endpoints
RECORD_ENDPOINT = "http://localhost:5000/start"
GET_TASK_ENDPOINT = "http://localhost:5001/get_task"
COMPLETE_TASK_ENDPOINT = "http://localhost:5001/complete_task"
ANALYZE_ENDPOINT = "http://localhost:5002/analyze"
DB_INSERT_ENDPOINT = "http://localhost:5003/db_insert"
DB_READ_ENDPOINT = "http://localhost:5003/db_read"
FILE_WRITE_ENDPOINT = "http://localhost:5003/write_results_to_file"

# BIRDSONG CONFIG
BIRD_SONG_FORMAT = '.mp3'


# Database schema
DATABASE_SCHEMA = """
DROP TABLE IF EXISTS detections;
CREATE TABLE IF NOT EXISTS detections (
  Date DATE,
  Time TIME,
  Sci_Name VARCHAR(100) NOT NULL,
  Com_Name VARCHAR(100) NOT NULL,
  Confidence FLOAT,
  Lat FLOAT,
  Lon FLOAT,
  Cutoff FLOAT,
  Week INT,
  Sens FLOAT,
  Overlap FLOAT,
  Bird_Song_File_Name VARCHAR(100) NOT NULL,
  Source_File_Name VARCHAR(100) NOT NULL,
  Bird_Song_Duration FLOAT

);
CREATE INDEX detections_Com_Name ON detections (Com_Name);
CREATE INDEX detections_Date_Time ON detections (Date DESC, Time DESC);
"""
