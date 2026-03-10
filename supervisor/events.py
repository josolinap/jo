"""... (truncated)
            tmp_file = results_dir / f"{task_id}.json.tmp"
            tmp_file.write_text(json.dumps(result_data, ensure_ascii=False), encoding="utf-8")
            os.rename(tmp_file, result_file)