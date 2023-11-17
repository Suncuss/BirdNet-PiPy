import requests
import config
import time

def create_test_data():
    for i in range(5):
        response = requests.post(config.RECORD_ENDPOINT)
        print(response.json())
    print("Created test data")

def main_logic():
    while True:
        # Get a task
        response = requests.get(config.GET_TASK_ENDPOINT)
        if response.status_code == 404:
            print("No tasks available, Sleeping for 6 seconds...")
            time.sleep(6)
            continue
        task_id = response.json().get('task_id')
        file_name = response.json().get('file_name')
        print(f"Processing file {file_name} with task ID {task_id}")

        # Analyze the file
        response = requests.post(config.ANALYZE_ENDPOINT, json={"audio_file_path": f"audio_files/{file_name}"})
        if response.status_code != 200:
            print("Error analyzing file, retrying in 3 seconds...")
            time.sleep(3)
            continue
        results = response.json()

        for result in results:
            # Write to log file
            log_file_name = file_name.split('.')[0] + '.txt'
            print(f"Writing {result} to log file {log_file_name}")
            response = requests.post(config.FILE_WRITE_ENDPOINT, json={"file_name": log_file_name, "data": result})
            # Write to the database
            print(f"Inserting {result} into the database")
            response = requests.post(config.DB_INSERT_ENDPOINT, json=result)
            if not response.json().get('success'):
                print("Error inserting into database, retrying in 3 seconds...")
                time.sleep(3)
                continue
        
        # Complete the task
        response = requests.post(config.COMPLETE_TASK_ENDPOINT, json={"task_id": task_id, "file_name": file_name})
        print("Completed task")

    