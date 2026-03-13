from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional
import pathlib
import requests
import json
from urllib.parse import urljoin

REPO_DIR = Path(os.environ.get("OUROBOROS_REPO_DIR", "/content/ouroboros_repo"))

# GitHub API integration (no gh CLI needed)
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
    
    def list_issues(self, repo: str, state: str = "open") -> List[Dict[str, Any]]:
        endpoint = f"/repos/{repo}/issues?state={state}"
        result = self.get(endpoint)
        if "error" in result:
            return []
        return result
    
    def get_issue(self, repo: str, issue_number: int) -> Dict[str, Any]:
        endpoint = f"/repos/{repo}/issues/{issue_number}"
        result = self.get(endpoint)
        return result
    
    def create_issue(self, repo: str, title: str, body: str = "") -> Dict[str, Any]:
        endpoint = f"/repos/{repo}/issues"
        data = {
            "title": title,
            "body": body,
        }
        return self.post(endpoint, data)
    
    def update_issue(self, repo: str, issue_number: int, data: Dict[str, Any]) -> Dict[str, Any]:
        endpoint = f"/repos/{repo}/issues/{issue_number}"
        return self.put(endpoint, data)
    
    def close_issue(self, repo: str, issue_number: int) -> Dict[str, Any]:
        data = {"state": "closed"}
        return self.update_issue(repo, issue_number, data)
    
    def comment_on_issue(self, repo: str, issue_number: int, body: str) -> Dict[str, Any]:
        endpoint = f"/repos/{repo}/issues/{issue_number}/comments"
        data = {"body": body}
        return self.post(endpoint, data)

# Initialize GitHub API client
github_client = GitHubAPI()


def import_test() -> Dict[str, Any]:
    exe = sys.executable if (isinstance(sys.executable, str) and os.path.isfile(sys.executable)) else "python"

    kwargs: Dict[str, Any] = {
        "cwd": str(REPO_DIR),
        "capture_output": True,
        "text": True,
    }
    if os.name == "nt":
        kwargs["shell"] = True

    try:
        r = subprocess.run([exe, "-c", "import ouroboros, ouroboros.agent; print('import_ok')"], **kwargs)
        return {
            "ok": (r.returncode == 0),
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": r.returncode,
        }
    except Exception as e:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"import_test_exception: {e}",
            "returncode": -1,
        }


def init(
    repo_dir: pathlib.Path,
    drive_root: pathlib.Path,
    remote_url: str,
    branch_dev: str,
    branch_stable: str,
) -> None:
    pass


def ensure_repo_present() -> None:
    pass


def checkout_and_reset(branch: str) -> None:
    pass


def sync_runtime_dependencies() -> None:
    pass


def safe_restart() -> None:
    pass

# GitHub API operations (replacing gh CLI)
def list_github_issues(repo: str = "josolinap/jo") -> List[Dict[str, Any]]:
    """List GitHub issues for the specified repository."""
    return github_client.list_issues(repo)

def get_github_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    """Get a specific GitHub issue."""
    return github_client.get_issue(repo, issue_number)

def create_github_issue(repo: str, title: str, body: str = "") -> Dict[str, Any]:
    """Create a new GitHub issue."""
    return github_client.create_issue(repo, title, body)

def comment_on_issue(repo: str, issue_number: int, body: str) -> Dict[str, Any]:
    """Comment on a GitHub issue."""
    return github_client.comment_on_issue(repo, issue_number, body)

def close_github_issue(repo: str, issue_number: int) -> Dict[str, Any]:
    """Close a GitHub issue."""
    return github_client.close_issue(repo, issue_number)