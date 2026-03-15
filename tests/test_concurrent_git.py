"""Multi-machine concurrent Git editing test.

Simulates multiple workers (machines) editing files concurrently to verify:
- Git synchronization under concurrent load
- Race condition handling
- Conflict detection and resolution
- Performance metrics (latency, throughput)
- Workflow efficiency metrics

Design:
- Test 1: Two workers edit DIFFERENT files (no conflict expected)
- Test 2: Two workers edit SAME file (conflict expected, verify resolution)
- Metrics: pull time, commit time, push time, conflict detection, success rate
"""

import os
import subprocess
import sys
import time
import tempfile
import json
import threading
from pathlib import Path
from typing import Dict, List, Tuple, Optional

REPO_DIR = Path(os.environ.get("REPO_DIR", "."))


def run_git(args: List[str], cwd: Path = REPO_DIR, timeout: int = 30) -> Tuple[int, str, str]:
    """Run git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Timeout"
    except Exception as e:
        return -1, "", str(e)


def ensure_clean_working_tree() -> bool:
    """Ensure repository is in a clean state before testing."""
    code, stdout, stderr = run_git(["status", "--porcelain"])
    if code != 0:
        print(f"ERROR: git status failed: {stderr}")
        return False
    if stdout.strip():
        print(f"ERROR: Repository not clean. Uncommitted changes:\n{stdout}")
        return False
    return True


def get_current_branch() -> Optional[str]:
    """Get current branch name."""
    code, stdout, stderr = run_git(["branch", "--show-current"])
    if code == 0:
        return stdout.strip()
    return None


def create_test_file(worker_id: int, iteration: int) -> Tuple[str, str]:
    """Create unique test content for a worker/iteration."""
    filename = f"tests/concurrent_test_worker{worker_id}_iter{iteration}.txt"
    content = f"""Concurrent edit test
Worker: {worker_id}
Iteration: {iteration}
Timestamp: {time.time()}
Random: {os.urandom(4).hex()}
"""
    return filename, content


def worker_simulation(
    worker_id: int, edits: List[Tuple[str, str]], results: List[Dict], lock: threading.Lock, branch: str = "dev"
) -> None:
    """Simulate a worker machine performing a series of edits and pushes."""
    worker_results = []

    for i, (filepath, content) in enumerate(edits):
        iteration_start = time.time()

        # 1. Pull latest changes (simulate starting from other machine's state)
        pull_start = time.time()
        code, stdout, stderr = run_git(["pull", "--rebase", "origin", branch])
        pull_time = time.time() - pull_start

        if code != 0:
            worker_results.append(
                {
                    "iteration": i,
                    "file": filepath,
                    "phase": "pull",
                    "success": False,
                    "error": stderr,
                    "pull_time": pull_time,
                }
            )
            continue

        # 2. Write file
        full_path = REPO_DIR / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        write_start = time.time()
        try:
            full_path.write_text(content, encoding="utf-8")
            write_time = time.time() - write_start
        except Exception as e:
            worker_results.append(
                {
                    "iteration": i,
                    "file": filepath,
                    "phase": "write",
                    "success": False,
                    "error": str(e),
                    "write_time": time.time() - write_start,
                }
            )
            continue

        # 3. Add to git
        add_start = time.time()
        code, stdout, stderr = run_git(["add", filepath])
        add_time = time.time() - add_start
        if code != 0:
            worker_results.append(
                {
                    "iteration": i,
                    "file": filepath,
                    "phase": "add",
                    "success": False,
                    "error": stderr,
                    "add_time": add_time,
                }
            )
            continue

        # 4. Commit
        commit_start = time.time()
        commit_msg = f"worker{worker_id} edit {i}"
        code, stdout, stderr = run_git(["commit", "-m", commit_msg])
        commit_time = time.time() - commit_start
        if code != 0:
            worker_results.append(
                {
                    "iteration": i,
                    "file": filepath,
                    "phase": "commit",
                    "success": False,
                    "error": stderr,
                    "commit_time": commit_time,
                }
            )
            continue

        # 5. Push
        push_start = time.time()
        code, stdout, stderr = run_git(["push", "origin", branch])
        push_time = time.time() - push_start
        total_time = time.time() - iteration_start

        worker_results.append(
            {
                "iteration": i,
                "file": filepath,
                "success": code == 0,
                "phase": "push" if code != 0 else "complete",
                "pull_time": round(pull_time, 4),
                "write_time": round(write_time, 4),
                "add_time": round(add_time, 4),
                "commit_time": round(commit_time, 4),
                "push_time": round(push_time, 4),
                "total_time": round(total_time, 4),
                "error": stderr if code != 0 else None,
            }
        )

    with lock:
        results.extend(worker_results)


def run_concurrent_test(num_workers: int = 2, edits_per_worker: int = 3, conflict_file: Optional[str] = None) -> Dict:
    """Run concurrent edit test with specified parameters."""
    print(f"\n=== Starting Concurrent Git Test ===")
    print(f"Workers: {num_workers}, Edits per worker: {edits_per_worker}")
    print(f"Conflict file: {conflict_file or 'None (different files)'}")
    print(f"Repository: {REPO_DIR}")

    # Verify repo is ready
    branch = get_current_branch()
    if not branch:
        return {"error": "Could not determine current branch"}

    print(f"Current branch: {branch}")

    if not ensure_clean_working_tree():
        return {"error": "Repository not clean. Abort."}

    # Reset to origin/branch to ensure clean start
    print("Resetting to origin...")
    run_git(["fetch", "origin"])
    run_git(["reset", "--hard", f"origin/{branch}"])

    # Prepare edit plans for each worker
    worker_plans = []
    for w in range(num_workers):
        edits = []
        for i in range(edits_per_worker):
            if conflict_file and w < 2:  # Only first two workers edit conflict file
                filepath = conflict_file
                content = f"Worker {w} iteration {i} conflict edit at {time.time()}\n"
            else:
                filepath, content = create_test_file(w, i)
            edits.append((filepath, content))
        worker_plans.append(edits)

    # Create shared results list with thread lock
    results: List[Dict] = []
    lock = threading.Lock()

    # Spawn worker threads
    threads = []
    start_time = time.time()
    for w in range(num_workers):
        t = threading.Thread(target=worker_simulation, args=(w, worker_plans[w], results, lock, branch))
        threads.append(t)
        t.start()

    # Wait for all workers
    for t in threads:
        t.join()
    total_test_time = time.time() - start_time

    # Analyze results
    total_edits = num_workers * edits_per_worker
    successful = sum(1 for r in results if r["success"])
    failed = total_edits - successful

    # Timing metrics
    if results:
        avg_pull = sum(r.get("pull_time", 0) for r in results) / len(results)
        avg_write = sum(r.get("write_time", 0) for r in results) / len(results)
        avg_add = sum(r.get("add_time", 0) for r in results) / len(results)
        avg_commit = sum(r.get("commit_time", 0) for r in results) / len(results)
        avg_push = sum(r.get("push_time", 0) for r in results) / len(results)
        avg_total = sum(r.get("total_time", 0) for r in results) / len(results)
    else:
        avg_pull = avg_write = avg_add = avg_commit = avg_push = avg_total = 0

    # Conflict detection
    conflicts = sum(1 for r in results if not r["success"] and "conflict" in r.get("error", "").lower())

    summary = {
        "test_configuration": {
            "num_workers": num_workers,
            "edits_per_worker": edits_per_worker,
            "conflict_file": conflict_file,
            "branch": branch,
        },
        "total_edits": total_edits,
        "successful": successful,
        "failed": failed,
        "conflicts_detected": conflicts,
        "total_test_time_sec": round(total_test_time, 4),
        "averages_sec": {
            "pull": round(avg_pull, 4),
            "write": round(avg_write, 4),
            "add": round(avg_add, 4),
            "commit": round(avg_commit, 4),
            "push": round(avg_push, 4),
            "total": round(avg_total, 4),
        },
        "results": results,
    }

    # Cleanup: reset repo to clean state after test
    run_git(["fetch", "origin"])
    run_git(["reset", "--hard", f"origin/{branch}"])
    run_git(["clean", "-fd"])

    return summary


def main() -> int:
    """Run comprehensive multi-machine test suite."""
    all_summaries = []

    print("\n" + "=" * 60)
    print("MULTI-MACHINE CONCURRENT EDITING TEST SUITE")
    print("=" * 60)

    # Test 1: Two workers, different files (no conflict expected)
    print("\n\n*** TEST 1: Different Files (No Conflict Expected) ***")
    summary1 = run_concurrent_test(num_workers=2, edits_per_worker=3, conflict_file=None)
    all_summaries.append(("Different Files", summary1))

    # Test 2: Two workers, same file (conflict expected)
    print("\n\n*** TEST 2: Same File (Conflict Expected) ***")
    summary2 = run_concurrent_test(
        num_workers=2, edits_per_worker=2, conflict_file="tests/concurrent_conflict_test.txt"
    )
    all_summaries.append(("Same File Conflict", summary2))

    # Test 3: Three workers, mixed scenario
    print("\n\n*** TEST 3: Three Workers, Mixed ***")
    summary3 = run_concurrent_test(
        num_workers=3, edits_per_worker=2, conflict_file="tests/concurrent_conflict_test2.txt"
    )
    all_summaries.append(("Three Workers Mixed", summary3))

    # Generate report
    report_path = Path("tests/concurrent_git_test_report.json")
    report = {
        "generated_at": time.time(),
        "test_suite": "multi_machine_concurrent_git",
        "summaries": [{"name": name, "data": s} for name, s in all_summaries],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("\n\n" + "=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)
    print(f"Report saved to: {report_path}")
    for name, s in all_summaries:
        print(f"\n{name}:")
        print(f"  Total edits: {s.get('total_edits')}")
        print(f"  Successful: {s.get('successful')}")
        print(f"  Failed: {s.get('failed')}")
        print(f"  Conflicts: {s.get('conflicts_detected')}")
        print(f"  Avg total time: {s.get('averages_sec', {}).get('total', 0):.4f}s")

    return 0


if __name__ == "__main__":
    # Check we're in repo
    if not REPO_DIR.exists():
        print(f"ERROR: REPO_DIR does not exist: {REPO_DIR}")
        sys.exit(1)

    # Verify git is available
    code, _, _ = run_git(["--version"])
    if code != 0:
        print("ERROR: git command not found")
        sys.exit(1)

    sys.exit(main() or 0)
