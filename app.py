import requests

def create_test_data():
    for i in range(5):
        response = requests.post("http://127.0.0.1:5000/start")
        print(response.json())
    print("Created test data")

def main_logic():
    # Get a task
    response = requests.get("http://127.0.0.1:5001/get_task")
    task_id = response.json().get('task_id')
    file_name = response.json().get('file_name')
    print(f"Processing file {file_name} with task ID {task_id}")

    # Analyze the file
    response = requests.post("http://127.0.0.1:5002/analyze", json={"audio_file_path": f"audio_files/{file_name}"})
    data = response.json()
    print(data)

    for result in data:
        # Write to the database
        print(f"Inserting {result} into the database")
        response = requests.post("http://127.0.0.1:5003/insert", json=result)
    
    # Complete the task
    response = requests.post("http://127.0.0.1:5001/complete_task", json={"task_id": task_id, "file_name": file_name})
    print("Completed task")

    