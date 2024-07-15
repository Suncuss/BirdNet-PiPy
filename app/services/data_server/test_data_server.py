import pytest
from data_server import app
import json

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_featured_bird(client):
    response = client.get('/api/featured_bird')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'name' in data
    assert 'scientificName' in data
    assert 'audioUrl' in data
    assert 'imageUrl' in data

def test_recent_detections(client):
    response = client.get('/api/recent_detections')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0
    assert 'id' in data[0]
    assert 'species' in data[0]
    assert 'timestamp' in data[0]
    assert 'confidence' in data[0]
    assert 'audioUrl' in data[0]
    assert 'spectrogramUrl' in data[0]

def test_detection_statistics(client):
    response = client.get('/api/detection_statistics')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert 'today' in data
    assert 'week' in data
    assert 'month' in data
    assert 'allTime' in data
    for period in data.values():
        assert 'totalDetections' in period
        assert 'uniqueSpecies' in period
        assert 'mostActiveHour' in period
        assert 'mostCommonBird' in period
        assert 'rarestBird' in period

def test_hourly_detection_data(client):
    response = client.get('/api/hourly_detection_data')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) == 24
    assert 'hour' in data[0]
    assert 'count' in data[0]

def test_detail_bird_detection_data(client):
    response = client.get('/api/detail_bird_detection_data')
    assert response.status_code == 200
    data = json.loads(response.data)
    assert isinstance(data, list)
    assert len(data) > 0
    assert 'species' in data[0]
    assert 'hourlyDetections' in data[0]
    assert 'totalDetections' in data[0]
    assert 'activeStart' in data[0]
    assert 'activeEnd' in data[0]