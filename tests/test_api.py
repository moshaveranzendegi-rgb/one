import unittest
from fastapi.testclient import TestClient
from app.api import app
from app.security import ACCESS_TOKEN


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_is_public_and_reports_rs_ai(self):
        response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['app'], 'RS-ai')

    def test_status_requires_access_token(self):
        response = self.client.get('/api/status')
        self.assertEqual(response.status_code, 401)

    def test_status_accepts_valid_access_token(self):
        response = self.client.get('/api/status', headers={'X-RS-AI-Token': ACCESS_TOKEN})
        self.assertEqual(response.status_code, 200)
        self.assertIn('ffmpeg', response.json())

    def test_home_and_static_assets_are_served(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('RS ai', response.text)
        js = self.client.get('/static/app.js')
        self.assertEqual(js.status_code, 200)
        self.assertIn('clothing_mode', js.text)

    def test_job_history_requires_access_token(self):
        response = self.client.get('/api/jobs')
        self.assertEqual(response.status_code, 401)


if __name__ == '__main__':
    unittest.main()
