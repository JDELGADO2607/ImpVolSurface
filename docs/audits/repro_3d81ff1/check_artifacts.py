"""Run pytest or the pipeline inside an extracted commit and compare artifacts."""
import argparse
import csv
import hashlib
from pathlib import Path
import subprocess
import sys
import time


def snapshot(root):
    files = set(root.glob("outputs/**/*"))
    files.update(root.glob("docs/**/*"))
    return {
        f.relative_to(root).as_posix(): (
            hashlib.sha256(data).hexdigest(),
            hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest(),
            f.stat().st_mtime_ns,
        )
        for f in sorted(files)
        if f.is_file() and not f.is_symlink()
        for data in [f.read_bytes()]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("mode", choices=("pytest", "pipeline"))
    parser.add_argument("log", type=Path)
    args = parser.parse_args()
    args.log = args.log.resolve()
    root = args.root.resolve()
    before = snapshot(root)
    tail = ["-m", "pytest", "-vv"] if args.mode == "pytest" else ["-u", "run_all.py"]
    start = time.monotonic()
    with args.log.open("wb") as f:
        result = subprocess.run([sys.executable, *tail], cwd=root, stdout=f, stderr=subprocess.STDOUT)
    after = snapshot(root)
    with args.log.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(("path", "status", "before_sha256", "after_sha256", "mtime_changed"))
        for path in sorted(before.keys() | after.keys()):
            old = before.get(path, ("", "", None))
            new = after.get(path, ("", "", None))
            if path not in before:
                status = "ADDED"
            elif path not in after:
                status = "MISSING"
            elif old[0] == new[0]:
                status = "EXACT"
            elif path.endswith((".csv", ".md", ".txt", ".json")) and old[1] == new[1]:
                status = "LINE_ENDINGS"
            else:
                status = "CHANGED"
            writer.writerow((path, status, old[0], new[0], old[2] != new[2]))
    print(f"{args.mode} python_exit={result.returncode} elapsed_s={time.monotonic()-start:.2f}", flush=True)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
