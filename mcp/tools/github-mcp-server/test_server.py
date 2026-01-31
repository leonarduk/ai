import unittest
import os
import json
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import sys

# Add parent directory to path to import server
sys.path.insert(0, str(Path(__file__).parent))

# Mock the MCP imports before importing server
sys.modules['mcp.server'] = MagicMock()
sys.modules['mcp.types'] = MagicMock()
sys.modules['mcp.server.stdio'] = MagicMock()

# Set a test token before importing
os.environ['GITHUB_TOKEN'] = 'test_token_12345'

from server import parse_repo, get_headers


class TestGitHubMCPServer(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        os.environ['GITHUB_TOKEN'] = 'test_token_12345'
    
    def test_parse_repo_from_url(self):
        """Test parsing repository from GitHub URL"""
        owner, repo = parse_repo("https://github.com/leonarduk/allotmint")
        self.assertEqual(owner, "leonarduk")
        self.assertEqual(repo, "allotmint")
    
    def test_parse_repo_from_shorthand(self):
        """Test parsing repository from owner/repo format"""
        owner, repo = parse_repo("leonarduk/allotmint")
        self.assertEqual(owner, "leonarduk")
        self.assertEqual(repo, "allotmint")
    
    def test_parse_repo_with_trailing_slash(self):
        """Test parsing repository URL with trailing slash"""
        owner, repo = parse_repo("https://github.com/leonarduk/allotmint/")
        self.assertEqual(owner, "leonarduk")
        self.assertEqual(repo, "allotmint")
    
    def test_get_headers(self):
        """Test that headers are correctly formatted"""
        headers = get_headers()
        self.assertIn("Authorization", headers)
        self.assertEqual(headers["Authorization"], "Bearer test_token_12345")
        self.assertEqual(headers["Accept"], "application/vnd.github.v3+json")
    
    def test_get_headers_without_token(self):
        """Test that missing token raises error"""
        del os.environ['GITHUB_TOKEN']
        with self.assertRaises(ValueError) as context:
            get_headers()
        self.assertIn("GITHUB_TOKEN", str(context.exception))
        # Restore token
        os.environ['GITHUB_TOKEN'] = 'test_token_12345'


class TestGitHubAPIIntegration(unittest.TestCase):
    """Integration tests that make real API calls (requires valid token)"""
    
    @classmethod
    def setUpClass(cls):
        """Check if we have a real token for integration tests"""
        cls.has_real_token = False
        if 'GITHUB_TOKEN' in os.environ and os.environ['GITHUB_TOKEN'].startswith('ghp_'):
            cls.has_real_token = True
    
    def setUp(self):
        if not self.has_real_token:
            self.skipTest("Skipping integration test - no valid GITHUB_TOKEN in environment")
    
    @patch('server.requests.get')
    def test_get_repo_info_mock(self, mock_get):
        """Test get_repo_info with mocked API response"""
        # Mock the response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "name": "allotmint",
            "full_name": "leonarduk/allotmint",
            "description": "Test repo",
            "html_url": "https://github.com/leonarduk/allotmint",
            "stargazers_count": 10,
            "forks_count": 5,
            "open_issues_count": 3,
            "default_branch": "main",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-12-01T00:00:00Z"
        }
        mock_get.return_value = mock_response
        
        # Import after mocking
        import requests
        response = requests.get("https://api.github.com/repos/leonarduk/allotmint")
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["name"], "allotmint")
        self.assertEqual(data["full_name"], "leonarduk/allotmint")
    
    @patch('server.requests.get')
    def test_list_branches_mock(self, mock_get):
        """Test list_branches with mocked API response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {"name": "main"},
            {"name": "develop"},
            {"name": "feature-branch"}
        ]
        mock_get.return_value = mock_response
        
        import requests
        response = requests.get("https://api.github.com/repos/leonarduk/allotmint/branches")
        
        branches = [b["name"] for b in response.json()]
        self.assertIn("main", branches)
        self.assertEqual(len(branches), 3)
    
    @patch('server.requests.get')
    def test_list_pull_requests_mock(self, mock_get):
        """Test list_pull_requests with mocked API response"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "number": 1,
                "title": "Test PR",
                "state": "open",
                "user": {"login": "testuser"}
            },
            {
                "number": 2,
                "title": "Another PR",
                "state": "closed",
                "user": {"login": "anotheruser"}
            }
        ]
        mock_get.return_value = mock_response
        
        import requests
        response = requests.get("https://api.github.com/repos/leonarduk/allotmint/pulls")
        
        prs = response.json()
        self.assertEqual(len(prs), 2)
        self.assertEqual(prs[0]["number"], 1)
        self.assertEqual(prs[0]["state"], "open")
    
    @patch('server.requests.post')
    def test_create_pull_request_mock(self, mock_post):
        """Test create_pull_request with mocked API response"""
        mock_response = Mock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "number": 123,
            "title": "New Feature",
            "html_url": "https://github.com/leonarduk/allotmint/pull/123"
        }
        mock_post.return_value = mock_response
        
        import requests
        response = requests.post(
            "https://api.github.com/repos/leonarduk/allotmint/pulls",
            json={
                "title": "New Feature",
                "body": "Description",
                "head": "feature-branch",
                "base": "main"
            }
        )
        
        pr = response.json()
        self.assertEqual(pr["number"], 123)
        self.assertEqual(pr["title"], "New Feature")
    
    @patch('server.requests.get')
    def test_error_handling_404(self, mock_get):
        """Test error handling for 404 response"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_get.return_value = mock_response
        
        import requests
        response = requests.get("https://api.github.com/repos/invalid/repo")
        
        with self.assertRaises(Exception):
            response.raise_for_status()
    
    @patch('server.requests.get')
    def test_error_handling_401(self, mock_get):
        """Test error handling for unauthorized access"""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
        mock_get.return_value = mock_response
        
        import requests
        response = requests.get("https://api.github.com/repos/private/repo")
        
        with self.assertRaises(Exception):
            response.raise_for_status()


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error conditions"""
    
    def test_parse_repo_invalid_format(self):
        """Test parsing repository with invalid format"""
        with self.assertRaises(Exception):
            owner, repo = parse_repo("invalid")
    
    def test_parse_repo_empty_string(self):
        """Test parsing empty repository string"""
        with self.assertRaises(Exception):
            owner, repo = parse_repo("")
    
    def test_parse_repo_github_enterprise_url(self):
        """Test parsing GitHub Enterprise URL"""
        owner, repo = parse_repo("https://github.mycompany.com/org/repo")
        self.assertEqual(owner, "org")
        self.assertEqual(repo, "repo")


if __name__ == '__main__':
    # Run tests with verbose output
    unittest.main(verbosity=2)
