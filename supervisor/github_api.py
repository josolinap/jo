from __future__ import annotations
import os
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin
import requests

class GitHubAPI:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.base_url = "https://api.github.com"
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json",
        }
        if self.token:
            self.headers["Authorization"] = f"Bearer {self.token}"
    
    def get(self, endpoint: str) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status_code": getattr(response, "status_code", None)}
    
    def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status_code": getattr(response, "status_code", None)}
    
    def put(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        try:
            response = requests.put(url, headers=self.headers, json=data, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e), "status_code": getattr(response, "status_code", None)}
    
    def delete(self, endpoint: str) -> Dict[str, Any]:
        url = urljoin(self.base_url, endpoint)
        try:
            response = requests.delete(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return {"status": "deleted"}
        except Exception as e:
            return {"error": str(e), "status_code": getattr(response, "status_code", None)}

# Initialize global client
github_client = GitHubAPI()

# Public API functions
def list_github_issues(repo: str = "josolinap/jo") -> List[Dict[str, Any]]:
    result = github_client.list_issues(repo)
    return result if isinstance(result, list) else []

def get_github_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    return github_client.get_issue(repo, issue_number)

def create_github_issue(repo: str, title: str, body: str = "") -> Dict[str, Any]:
    return github_client.create_issue(repo, title, body)

def comment_on_issue(repo: str, issue_number: int, body: str) -> Dict[str, Any]:
    return github_client.comment_on_issue(repo, issue_number, body)

def close_github_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    return github_client.close_issue(repo, issue_number)