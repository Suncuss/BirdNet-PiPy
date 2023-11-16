from flask import Flask, request, g, jsonify
import sqlite3
import config

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
  File_Name VARCHAR(100) NOT NULL
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

@app.route('/insert', methods=['POST'])
def insert_data():
    data = request.json
    db = get_db()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO detections (Date, Time, Sci_Name, Com_Name, Confidence, Lat, Lon, Cutoff, Week, Sens, Overlap, File_Name) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (data['Date'], data['Time'], data['Sci_Name'], data['Com_Name'], 
                  data['Confidence'], data['Lat'], data['Lon'], data['Cutoff'], 
                  data['Week'], data['Sens'], data['Overlap'], data['File_Name']))

        db.commit()
        return jsonify(success=True)
    except sqlite3.Error as e:
        db.rollback()
        return jsonify(success=False, error=str(e))


@app.route('/read', methods=['GET'])
@app.route('/read', methods=['GET'])
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


if __name__ == '__main__':
    app.run(debug=True, port=5003)

