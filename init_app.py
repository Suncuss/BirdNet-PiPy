import sqlite3

def create_database(db_path, schema):
    """
    Create a new SQLite database based on the provided schema.

    :param db_path: Path to the SQLite database file.
    :param schema: SQL schema to create tables.
    """
    connection = sqlite3.connect(db_path)
    with connection:
        connection.executescript(schema)

def setup_app(app_config):
    """
    Set up the application including the database.

    :param app_config: Configuration dictionary for the application.
    """
    create_database(app_config['DATABASE_PATH'], app_config['DATABASE_SCHEMA'])
    # Additional setup tasks can be added here


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
  File_Name VARCHAR(100) NOT NULL
);
CREATE INDEX detections_Com_Name ON detections (Com_Name);
CREATE INDEX detections_Date_Time ON detections (Date DESC, Time DESC);
"""

