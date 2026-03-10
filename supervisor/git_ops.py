def import_test() -> Dict[str, Any]:
    import sys

    # Determine executable: prefer sys.executable if it exists, else "python"
    exe = sys.executable if (isinstance(sys.executable, str) and os.path.isfile(sys.executable)) else "python"

    # On Windows, using shell=True helps with paths containing spaces
    kwargs: Dict[str, Any] = {
        "cwd": str(REPO_DIR),
        "capture_output": True,
        "text": True,
    }
    if os.name == "nt":
        kwargs["shell"] = True

    try:
        r = subprocess.run(
            [exe, "-c", "import ouroboros, ouroboros.agent; print('import_ok')"],
            **kwargs
        )
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