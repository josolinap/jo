"""GitHub Issues mailbox for ChatGPT -> Jo.

This bridge is designed for Jo running on ephemeral GitHub Actions runners.
ChatGPT (or another trusted operator) creates an issue titled with the
configured prefix, Jo picks it up, executes it through the normal worker
system, posts the result as an issue comment, and closes the issue.

No external server, paid API, tunnel, or always-on VM is required.
"""

from __future__ import annotations

import json
import os
import pathlib
import time
from typing import Any, Dict, List, Optional, Set

import requests


class GitHubInbox:
    def __init__(self, data_root: pathlib.Path) -> None:
        self.data_root = pathlib.Path(data_root)
        self.state_path = self.data_root / "state" / "github_inbox.json"
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

        self.token = os.environ.get("GITHUB_TOKEN", "").strip()
        self.owner = os.environ.get("GITHUB_USER", "").strip()
        self.repo = os.environ.get("GITHUB_REPO", "").strip()
        self.prefix = os.environ.get("JO_GITHUB_INBOX_PREFIX", "[JO]").strip() or "[JO]"
        allowed = os.environ.get("JO_GITHUB_ALLOWED_USERS", self.owner).strip()
        self.allowed_users: Set[str] = {name.strip().lower() for name in allowed.split(",") if name.strip()}
        try:
            self.timeout = max(5.0, float(os.environ.get("JO_GITHUB_INBOX_TIMEOUT_SEC", "15")))
        except (TypeError, ValueError):
            self.timeout = 15.0
        try:
            self.poll_interval_sec = max(5.0, float(os.environ.get("JO_GITHUB_INBOX_POLL_SEC", "30")))
        except (TypeError, ValueError):
            self.poll_interval_sec = 30.0

        self._last_error = ""
        self.base_url = f"https://api.github.com/repos/{self.owner}/{self.repo}"
        self._state = self._load_state()

    @property
    def enabled(self) -> bool:
        return bool(self.token and self.owner and self.repo and os.environ.get("JO_GITHUB_INBOX_ENABLED", "1").strip().lower() not in {"0", "false", "no"})

    def _load_state(self) -> Dict[str, Any]:
        try:
            if self.state_path.exists():
                data = json.loads(self.state_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
        return {"claims": {}, "last_poll": 0.0}

    def _save_state(self) -> None:
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.state_path)

    def _headers(self) -> Dict[str, str]:
        return {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}", "X-GitHub-Api-Version": "2022-11-28"}

    def _request(self, method: str, path: str, **kwargs: Any) -> Optional[requests.Response]:
        try:
            response = requests.request(method, f"{self.base_url}{path}", headers=self._headers(), timeout=self.timeout, **kwargs)
            if response.status_code >= 400:
                self._last_error = f"{method} {path}: HTTP {response.status_code} {response.text[:300]}"
                return None
            self._last_error = ""
            return response
        except Exception as exc:
            self._last_error = f"{method} {path}: {type(exc).__name__}: {exc}"
            return None

    def poll(self) -> List[Dict[str, Any]]:
        """Return newly claimed [JO] issues as normal Jo tasks."""
        if not self.enabled:
            return []
        response = self._request("GET", "/issues", params={"state": "open", "sort": "created", "direction": "asc", "per_page": 20})
        if response is None:
            return []
        try:
            issues = response.json()
        except Exception:
            return []
        claims = self._state.setdefault("claims", {})
        tasks: List[Dict[str, Any]] = []
        for issue in issues if isinstance(issues, list) else []:
            number = issue.get("number")
            title = str(issue.get("title") or "")
            author = str((issue.get("user") or {}).get("login") or "").lower()
            body = str(issue.get("body") or "").strip()
            if not number or not title.startswith(self.prefix + " "):
                continue
            if self.allowed_users and author not in self.allowed_users:
                continue
            if str(number) in claims or not body:
                continue
            task_id = f"gh{number:x}"
            claims[str(number)] = {
                "task_id": task_id,
                "claimed_at": time.time(),
                "title": title,
                "url": issue.get("html_url") or "",
                "author": author,
            }
            task_kind = "evolution" if title[len(self.prefix) + 1:].strip().lower() in {"evolve", "evolution"} else "task"
            tasks.append({
                "id": task_id,
                "type": task_kind,
                "chat_id": 0,
                "text": body,
                "_github_issue": int(number),
                "_github_issue_url": issue.get("html_url") or "",
                "_github_issue_title": title,
                "_github_issue_author": author,
            })
        self._state["last_poll"] = time.time()
        self._save_state()
        return tasks

    def complete(self, task_id: str, result: str, failed: bool = False) -> bool:
        """Publish a worker result to its originating GitHub issue and close it."""
        claims = self._state.setdefault("claims", {})
        issue_number: Optional[str] = None
        for number, claim in claims.items():
            if str(claim.get("task_id")) == str(task_id):
                issue_number = number
                break
        if issue_number is None:
            return False
        status = "FAILED" if failed else "COMPLETED"
        body = str(result or "").strip() or "Jo finished the task without a textual response."
        comment = "### Jo " + status + "\n\n" + body[:7000] + "\n\n---\nTask ID: " + str(task_id)
        posted = self._request("POST", f"/issues/{issue_number}/comments", json={"body": comment})
        if posted is None:
            return False
        closed = self._request("PATCH", f"/issues/{issue_number}", json={"state": "closed", "state_reason": "completed"})
        if closed is None:
            return False
        claims.pop(issue_number, None)
        self._save_state()
        return True

    def recover_stale_claims(self, max_age_sec: int = 8 * 3600) -> None:
        """Release abandoned claims after a long runner outage."""
        claims = self._state.setdefault("claims", {})
        now = time.time()
        changed = False
        for number, claim in list(claims.items()):
            claimed_at = float(claim.get("claimed_at") or 0)
            if claimed_at and now - claimed_at > max_age_sec:
                claims.pop(number, None)
                changed = True
        if changed:
            self._save_state()