from flask import Flask, request, jsonify
import os
import shutil
import uuid
import config

app = Flask(__name__)


# Utility Functions
def get_next_file():
    # only list wav files
    files = os.listdir(config.INCOMING_DIR)
    files = [f for f in files if f.endswith('.wav')]
    files.sort()
    print("Files in incoming directory: ", files)
    try:
        return files[0]  # Get the first file in the directory
    except IndexError:
        return None  # No files available

def move_file_to_processed(file_name):
    shutil.move(os.path.join(config.INCOMING_DIR, file_name), os.path.join(config.PROCESSED_DIR, file_name))

# Dispatch Task Endpoint
@app.route('/get_task', methods=['GET'])
def get_task():
    file_name = get_next_file()
    if file_name:
        task_id = str(uuid.uuid4())  # Generate a unique task ID
        # In a real-world scenario, you would mark this task as in progress in your system
        return jsonify({"task_id": task_id, "file_name": file_name}), 200
    else:
        return jsonify({"message": "No tasks available"}), 404

# Complete Task Endpoint
@app.route('/complete_task', methods=['POST'])
def complete_task():
    task_id = request.json.get('task_id')  # In a real-world scenario, you would use this to track the task
    file_name = request.json.get('file_name')
    move_file_to_processed(file_name)
    return jsonify({"message": f"Task {task_id} with file {file_name} completed"}), 200

if __name__ == '__main__':
    app.run(debug=True, port=5001)
