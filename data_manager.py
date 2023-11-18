from flask import Flask, request, g, jsonify
import sqlite3
import config
import os

app = Flask(__name__)
DATABASE = config.DATABASE_PATH

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
  Bird_Song_File_Name VARCHAR(100) NOT NULL
  Source_File_Name VARCHAR(100) NOT NULL
  Bird_Song_Duration FLOAT

);
CREATE INDEX detections_Com_Name ON detections (Com_Name);
CREATE INDEX detections_Date_Time ON detections (Date DESC, Time DESC);
"""

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/db_insert', methods=['POST'])
def insert_data():
    data = request.json
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO detections (Date, Time, Sci_Name, Com_Name, Confidence, Lat, Lon, Cutoff, Week, Sens, Bird_Song_File_Name) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data['Date'], data['Time'], data['Sci_Name'], data['Com_Name'], 
                  data['Confidence'], data['Lat'], data['Lon'], data['Cutoff'], 
                  data['Week'], data['Sens'], data['Bird_Song_File_Name']))

        db.commit()
        return jsonify(success=True)
    except sqlite3.Error as e:
        print("Error inserting data")
        print(e)
        db.rollback()
        return jsonify(success=False, error=str(e))


@app.route('/db_read', methods=['GET'])
def read_data():
    # NOT TESTED YET
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM detections")
        detections = cursor.fetchall()
        # Convert the response to a list of dicts to jsonify
        detections_list = []
        for detection in detections:
            detections_list.append({
                'Date': detection[0],
                'Time': detection[1],
                'Sci_Name': detection[2],
                'Com_Name': detection[3],
                'Confidence': detection[4],
                'Lat': detection[5],
                'Lon': detection[6],
                'Cutoff': detection[7],
                'Week': detection[8],
                'Sens': detection[9],
                'Overlap': detection[10],
                'File_Name': detection[11]
            })
        return jsonify(detections_list)
    except sqlite3.Error as e:
        return jsonify(success=False, error=str(e))

@app.route('/db_delete', methods=['DELETE'])
# TODO: Implement this function
def delete_data():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("DELETE FROM detections")
        db.commit()
        return jsonify(success=True)
    except sqlite3.Error as e:
        print("Error deleting data")
        print(e)
        db.rollback()
        return jsonify(success=False, error=str(e))
    
@app.route('/write_results_to_file', methods=['POST'])
def write_to_file():
    data = request.json
    file_name = data.get('file_name')
    file_path = config.PROCESS_LOG_DIR + file_name
    data = data.get('data')
    result_string = (
        f"{data['Date']},{data['Time']},{data['Sci_Name']},{data['Com_Name']},{data['Confidence']},"
        f"{data['Source_File_Name']},{data['Chunk_Index']},{data['Bird_Song_Duration']},{data['Bird_Song_File_Name']}\n"
    )
    # Append to file, if file exists
    if os.path.exists(file_path):
        with open(file_path, 'a') as f:
            f.write(result_string)
    # Create file, if file does not exist
    else:
        with open(file_path, 'w') as f:
            f.write("Date,Time,Sci_Name,Com_Name,Confidence,Source_File_Name,Chunk_Index,Bird_Song_Duration,Bird_Song_File_Name\n")
            f.write(result_string)
    
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(debug=True, port=5003)

