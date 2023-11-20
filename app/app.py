import os
import time
import requests

from configs import config

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
        response = requests.post(config.ANALYZE_ENDPOINT, json={"audio_file_path": f"{config.RECODING_DIR}/{file_name}"})
        if response.status_code != 200:
            print("Error analyzing file, retrying in 3 seconds...")
            time.sleep(3)
            continue
        detections = response.json()

        # Merge neighboring detections of the same species
        merged_detections = merge_detections(detections)
        
        for detection in merged_detections:
            # Generate the audio clip
            start_time = detection['Chunk_Index'] * config.RECORDING_CHUNK_LENGTH
            end_time = start_time + detection['Bird_Song_Duration']
            audio_file_path = os.path.join(config.RECODING_DIR, file_name)
            audio_clip_file_path = os.path.join(config.EXTRACTED_AUDIO_DIR, detection['Bird_Song_File_Name'])
            
            response = requests.post(config.AUDIO_TRIMING_ENDPOINT, json={
                "audio_file_path": audio_file_path,
                "start_time": start_time,
                "end_time": end_time,
                "trimmed_audio_file_path": audio_clip_file_path
            })

            # Generate the spectrogram
            spectrogram_file_path = os.path.join(config.SPECTROGRAM_DIR, detection['Bird_Song_File_Name'].split('.')[0] + '.png')
            response = requests.post(config.SPECTROGRAM_GENERATION_ENDPOINT, json={
                "audio_file_path": audio_clip_file_path,
                "spectrogram_file_path": spectrogram_file_path,
                "graph_title": f"{detection['Com_Name']} {detection['Date']} {detection['Time']}"
            })

            # Write the results to the log file
            log_file_name = file_name.split('.')[0] + '.csv'
            response = requests.post(config.LOGGING_ENDPOINT, json={"file_name": log_file_name, "data": detection})

        
        # Update the original detections with new file name in the merged detections
        update_original_detections(detections, merged_detections)
        DATA_BASE_WRITE_FAIL = False
        # Write the results to the database and log file
        for result in detections:
            # Write to the database
            print(f"Inserting {result} into the database")
            response = requests.post(config.DB_INSERT_ENDPOINT, json=result)
            if not response.json().get('success'):
                print("Error inserting into database, retrying in 3 seconds...")
                time.sleep(3)
                DATA_BASE_WRITE_FAIL = True
                break
        if DATA_BASE_WRITE_FAIL:
            # this will start the loop again and retry the whole file since the current file has never been completed
            # but if the insert failed in the middle of inserting results to db, then the the already inserted results might be re-inserted
            continue

        # Mark the task as complete
        response = requests.post(config.COMPLETE_TASK_ENDPOINT, json={"task_id": task_id, "file_name": file_name})
        print("Completed task")

            
def merge_detections(detections):
    if not detections:
        return []

    merged_detections = []
    prev_detection = None

    for detection in detections:
        if prev_detection and detection['Sci_Name'] == prev_detection['Sci_Name']:
            # Add the current detection's duration to the previous (merged) detection
            prev_detection["Bird_Song_Duration"] += detection["Bird_Song_Duration"]
        else:
            # If not a match, add the previous detection to the list (if it exists)
            if prev_detection:
                merged_detections.append(prev_detection)
            # Start a new merge group with a copy of the current detection
            prev_detection = detection.copy()

    # Add the last detection
    merged_detections.append(prev_detection)

    return merged_detections

def update_original_detections(original_detections, merged_detections):
    merged_index = 0
    for original in original_detections:
        if merged_index >= len(merged_detections):
            break

        # Update the filename if the Sci_Name matches
        if original['Sci_Name'] == merged_detections[merged_index]['Sci_Name']:
            original['Bird_Song_File_Name'] = merged_detections[merged_index]['Bird_Song_File_Name']
        else:
            # Move to the next merged detection if the Sci_Names do not match
            merged_index += 1

            # Check and update the filename for the current original detection again
            if original['Sci_Name'] == merged_detections[merged_index]['Sci_Name']:
                original['Bird_Song_File_Name'] = merged_detections[merged_index]['Bird_Song_File_Name']