import os

import sqlite3
from flask import Flask, request, g, jsonify

from ..configs import config

app = Flask(__name__)

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(config.DATABASE_PATH)
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


@app.route('/db_read_all', methods=['GET'])
def read_data():
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT * FROM detections")
        detections = cursor.fetchall()
        # Convert the response to a list of dicts to jsonify
        detections_list = []
        for detection in detections:
            detections_list.append({
                "id": detection[0],
                "Date": detection[1],
                "Time": detection[2],
                "Sci_Name": detection[3],
                "Com_Name": detection[4],
                "Confidence": detection[5],
                "Lat": detection[6],
                "Lon": detection[7],
                "Cutoff": detection[8],
                "Week": detection[9],
                "Sens": detection[10],
                "Bird_Song_File_Name": detection[11]
            })
        return jsonify(detections_list)
    except sqlite3.Error as e:
        return jsonify(success=False, error=str(e))

@app.route('/db_read_record_with_id', methods=['GET']) 
def db_read_record_with_id():
    record_id = request.args.get('id')
    db = get_db()
    cursor = db.cursor()
    try:
        # Prepare your query with a placeholder for the id
        cursor.execute("SELECT id, Date, Time, Sci_Name, Com_Name, Confidence, Lat, Lon, Cutoff, Week, Sens, Bird_Song_File_Name FROM detections WHERE id = ?", (record_id,))
        detection = cursor.fetchone()  # fetchone() retrieves a single record

        if detection is None:
            return jsonify(success=False, error="Record not found"), 404

        # Convert the response to a dict to jsonify
        detection = {
            "id": detection[0],
            "Date": detection[1],
            "Time": detection[2],
            "Sci_Name": detection[3],
            "Com_Name": detection[4],
            "Confidence": detection[5],
            "Lat": detection[6],
            "Lon": detection[7],
            "Cutoff": detection[8],
            "Week": detection[9],
            "Sens": detection[10],
            "Bird_Song_File_Name": detection[11]
        }
        return jsonify(detection)
    except sqlite3.Error as e:
        return jsonify(success=False, error=str(e)), 500


@app.route('/delete/<int:record_id>', methods=['DELETE'])
def delete_record(record_id):
    db = get_db()
    cursor = db.cursor()
    try:
        # Check if the record exists
        cursor.execute("SELECT 1 FROM detections WHERE id = ?", (record_id,))
        if cursor.fetchone() is None:
            return jsonify(success=False, error="Record not found"), 404

        # If the record exists, delete it
        cursor.execute("DELETE FROM detections WHERE id = ?", (record_id,))
        db.commit()

        return jsonify(success=True, message="Record deleted successfully")
    except sqlite3.Error as e:
        return jsonify(success=False, error=str(e)), 500

    
@app.route('/write_log_to_file', methods=['POST'])
def write_to_file():
    data = request.json
    file_name = data.get('file_name')
    file_path = os.path.join(config.PROCESS_LOG_DIR, file_name)
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

