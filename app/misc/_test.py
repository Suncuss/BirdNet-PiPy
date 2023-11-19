import unittest
import json
from job_dispatcher import app  # Replace with the name of your Flask app file

class FlaskAppTestCase(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_all(self):
        response = self.app.get('/get_task')
        self.assertEqual(response.status_code, 200)
        print(response.json)
        print(response.json.get('file_name'))

        complete_response = self.app.post('/complete_task', json={"task_id": response.json.get('task_id'), "file_name": response.json.get('file_name')})

        print(complete_response.status_code)

if __name__ == '__main__':
    unittest.main()
