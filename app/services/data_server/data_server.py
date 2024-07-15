from flask import Flask, jsonify, request
from faker import Faker
import random
from datetime import datetime, timedelta
from flask_cors import CORS
import requests
from urllib.parse import quote
from functools import lru_cache
import time


app = Flask(__name__)
CORS(app)  # This will enable CORS for all routes


fake = Faker()


# Simple in-memory cache
image_cache = {}
CACHE_EXPIRATION = 3600  # Cache expiration time in seconds (1 hour)

def get_cached_image(species_name):
    if species_name in image_cache:
        cached_data = image_cache[species_name]
        if time.time() - cached_data['timestamp'] < CACHE_EXPIRATION:
            print(f"Using cached image for {species_name}")
            return cached_data['url']
    return None

def set_cached_image(species_name, image_url):
    image_cache[species_name] = {
        'url': image_url,
        'timestamp': time.time()
    }

@lru_cache(maxsize=100)
def fetch_wikimedia_image(species_name):
    # Check cache first
    cached_url = get_cached_image(species_name)
    if cached_url:
        print(f"Returning cached image for {species_name}")
        return cached_url, None

    try:
        # Search for the page
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(species_name)}&format=json&origin=*"
        search_response = requests.get(search_url)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        if not search_data['query']['search']:
            return None, 'No results found'
        
        page_title = search_data['query']['search'][0]['title']

        # Fetch the image
        image_api_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={quote(page_title)}&prop=pageimages&format=json&pithumbsize=500&origin=*"
        image_response = requests.get(image_api_url)
        image_response.raise_for_status()
        image_data = image_response.json()

        pages = image_data['query']['pages']
        image_url = next(iter(pages.values())).get('thumbnail', {}).get('source')

        if image_url:
            # Cache the result
            set_cached_image(species_name, image_url)
            return image_url, None
        else:
            return None, 'No image found'

    except requests.RequestException as e:
        return None, f'Error fetching Wikimedia image: {str(e)}'
    


def generate_featured_bird():
    return {
        'name': 'Eastern Bluebird',
        'scientificName': 'Sialia sialis',
        'audioUrl': '/test.wav',
        'imageUrl': '/eb.jpeg'
    }

def generate_recent_detections():
    return [
        {
            'id': i,
            'species': fake.word(),
            'timestamp': (datetime.now() - timedelta(minutes=15*i)).isoformat(),
            'confidence': round(random.uniform(0.8, 1.0), 2),
            'audioUrl': f'https://example.com/{fake.word()}.mp3',
            'spectrogramUrl': '/spg.png'
        } for i in range(1, 4)
    ]

def generate_detection_statistics():
    return {
        period: {
            'totalDetections': random.randint(100, 10000),
            'uniqueSpecies': random.randint(10, 100),
            'mostActiveHour': f"{random.randint(4, 8)} AM - {random.randint(5, 9)} AM",
            'mostCommonBird': fake.word(),
            'rarestBird': fake.word()
        } for period in ['today', 'week', 'month', 'allTime']
    }

def generate_hourly_detection_data():
    return [
        {'hour': f"{hour}{'am' if hour < 12 else 'pm'}", 'count': random.randint(0, 100)}
        for hour in range(24)
    ]

def generate_bird_detection_data(num_species=10):
    birds = [fake.unique.word() for _ in range(num_species)]
    bird_data = []

    for species in birds:
        hourly_detections = [0] * 24
        earliest_possible_activity = random.randint(4, 6)
        latest_possible_activity = random.randint(18, 21)

        is_morning_bird = random.choice([True, False])
        is_afternoon_bird = random.choice([True, False])

        if is_morning_bird and not is_afternoon_bird:
            active_start = earliest_possible_activity
            active_end = random.randint(11, 14)
        elif not is_morning_bird and is_afternoon_bird:
            active_start = random.randint(10, 14)
            active_end = latest_possible_activity
        else:
            active_start = earliest_possible_activity
            active_end = latest_possible_activity

        num_bursts = random.randint(1, 3)
        burst_hours = sorted(random.sample(range(active_start, active_end + 1), num_bursts))

        for hour in burst_hours:
            burst_duration = random.randint(1, 2)
            for i in range(-1, burst_duration + 1):
                activity_hour = hour + i
                if active_start <= activity_hour <= active_end:
                    hourly_detections[activity_hour] += random.randint(5, 20)

        ramp_duration = random.randint(1, 3)
        for hour in range(active_start, active_start + ramp_duration):
            hourly_detections[hour] += random.randint(1, 5) * (hour - active_start + 1)
        for hour in range(active_end - ramp_duration + 1, active_end + 1):
            hourly_detections[hour] += random.randint(1, 5) * (active_end - hour + 1)

        for hour in range(active_start, active_end + 1):
            hourly_detections[hour] += random.randint(0, 3)

        bird_data.append({
            'species': species,
            'hourlyDetections': hourly_detections,
            'totalDetections': sum(hourly_detections),
            'activeStart': active_start,
            'activeEnd': active_end
        })

    bird_data.sort(key=lambda x: x['totalDetections'], reverse=True)
    return bird_data


@app.route('/api/featured_bird', methods=['GET'])
def get_featured_bird():
    return jsonify(generate_featured_bird())

@app.route('/api/recent_detections', methods=['GET'])
def get_recent_detections():
    return jsonify(generate_recent_detections())

@app.route('/api/detection_statistics', methods=['GET'])
def get_detection_statistics():
    return jsonify(generate_detection_statistics())

@app.route('/api/hourly_detection_data', methods=['GET'])
def get_hourly_detection_data():
    return jsonify(generate_hourly_detection_data())

@app.route('/api/detail_bird_detection_data', methods=['GET'])
def get_detail_bird_detection_data():
    return jsonify(generate_bird_detection_data(10))

@app.route('/api/wikimedia_image', methods=['GET'])
def get_wikimedia_image():
    species_name = request.args.get('species', '')
    if not species_name:
        return jsonify({'error': 'Species name is required'}), 400

    image_url, error = fetch_wikimedia_image(species_name)
    if error:
        return jsonify({'error': error}), 404 if 'No results found' in error else 500
    return jsonify({'imageUrl': image_url})


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)