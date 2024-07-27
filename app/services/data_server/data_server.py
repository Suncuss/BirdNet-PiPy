from flask import Flask, jsonify, request
from faker import Faker
from faker.providers import BaseProvider
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


# Define a list of bird names
bird_names = [
    "Northern Cardinal", "American Robin", "Blue Jay", "Mourning Dove",
    "Red-winged Blackbird", "House Sparrow", "European Starling",
    "Song Sparrow", "House Finch", "Eastern Bluebird"
]

# Custom provider class for bird names


class BirdProvider(BaseProvider):
    def bird_name(self):
        return random.choice(bird_names)


# Add the custom provider to Faker
fake.add_provider(BirdProvider)


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
        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={
            quote(species_name)}&format=json&origin=*"
        search_response = requests.get(search_url)
        search_response.raise_for_status()
        search_data = search_response.json()

        if not search_data['query']['search']:
            return None, 'No results found'

        page_title = search_data['query']['search'][0]['title']

        # Fetch the image
        image_api_url = f"https://en.wikipedia.org/w/api.php?action=query&titles={
            quote(page_title)}&prop=pageimages&format=json&pithumbsize=500&origin=*"
        image_response = requests.get(image_api_url)
        image_response.raise_for_status()
        image_data = image_response.json()

        pages = image_data['query']['pages']
        image_url = next(iter(pages.values())).get(
            'thumbnail', {}).get('source')

        if image_url:
            # Cache the result
            set_cached_image(species_name, image_url)
            return image_url, None
        else:
            return None, 'No image found'

    except requests.RequestException as e:
        return None, f'Error fetching Wikimedia image: {str(e)}'


def generate_latest_observation():
    species = fake.bird_name()
    image_url, _ = fetch_wikimedia_image(species)
    return {
        'name': species,
        'scientificName': "Unknownus birdus",
        'audioUrl': '/test.wav',
        'imageUrl': image_url or '/eb.jpeg',
        'timestamp': datetime.now().isoformat()
    }


def generate_recent_observations():
    return [
        {
            'id': i,
            'species': fake.bird_name(),
            'timestamp': (datetime.now() - timedelta(minutes=15*i)).isoformat(),
            'confidence': round(random.uniform(0.8, 1.0), 2),
            'audioUrl': f'/audio/{fake.bird_name().lower().replace(" ", "_")}.mp3',
            'spectrogramUrl': f'/spectrogram/{fake.bird_name().lower().replace(" ", "_")}.png'
        } for i in range(1, 6)  # Generating 5 recent observations
    ]


def generate_observation_summary():
    return {
        period: {
            'totalObservations': random.randint(100, 10000),
            'uniqueSpecies': random.randint(10, 100),
            'mostActiveHour': f"{random.randint(4, 8)} AM - {random.randint(5, 9)} AM",
            'mostCommonBird': fake.bird_name(),
            'rarestBird': fake.bird_name()
        } for period in ['today', 'week', 'month', 'allTime']
    }


def generate_hourly_activity_data():
    return [
        {'hour': f"{hour:02d}:00", 'count': random.randint(0, 100)}
        for hour in range(24)
    ]


def generate_bird_activity_data(num_species=10):
    fake = Faker()
    fake.add_provider(BirdProvider)
    birds = [fake.unique.bird_name() for _ in range(num_species)]
    bird_data = []

    for species in birds:
        hourly_activity = [0] * 24
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
                    hourly_activity[activity_hour] += random.randint(5, 20)

        ramp_duration = random.randint(1, 3)
        for hour in range(active_start, active_start + ramp_duration):
            hourly_activity[hour] += random.randint(1, 5) * (hour - active_start + 1)
        for hour in range(active_end - ramp_duration + 1, active_end + 1):
            hourly_activity[hour] += random.randint(1, 5) * (active_end - hour + 1)

        for hour in range(active_start, active_end + 1):
            hourly_activity[hour] += random.randint(0, 3)

        bird_data.append({
            'species': species,
            'hourlyActivity': hourly_activity,
            'totalObservations': sum(hourly_activity),
            'activeStart': active_start,
            'activeEnd': active_end
        })

    bird_data.sort(key=lambda x: x['totalObservations'], reverse=True)
    return bird_data

@app.route('/api/observation/latest', methods=['GET'])
def get_latest_observation():
    return jsonify(generate_latest_observation())

@app.route('/api/observations/recent', methods=['GET'])
def get_recent_observations():
    return jsonify(generate_recent_observations())

@app.route('/api/summary/stats', methods=['GET'])
def get_observation_summary():
    return jsonify(generate_observation_summary())

@app.route('/api/activity/hourly', methods=['GET'])
def get_hourly_activity():
    return jsonify(generate_hourly_activity_data())

@app.route('/api/activity/overview', methods=['GET'])
def get_activity_overview():
    return jsonify(generate_bird_activity_data(10))

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