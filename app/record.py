import requests
import configs.config as config
def create_test_data():
    while True:
        response = requests.post(config.RECORD_ENDPOINT)
        print(response.json())