#!/bin/bash

echo "Starting Flask microservices..."

# Start each service in the background and redirect output to a log file
python3 -m app.services.audio_server > logs/audio_server.log 2>&1 &
python3 -m app.services.birdnet_server > logs/birdnet_server.log 2>&1 &
python3 -m app.services.data_manager > logs/data_manager.log 2>&1 &
python3 -m app.services.job_dispatcher > logs/job_dispatcher.log 2>&1 &


echo "All services started."
