#!/usr/bin/env python3
"""
Axon Browser Worker - CLI Entry Point

Usage:
    # Run task from JSON string
    python main.py '{"profile_id": "k197eg5j", "task_type": "page_probe", "params": {"url": "https://www.xiaohongshu.com"}}'

    # Run task from file
    python main.py --file task.json

    # Pipe JSON
    echo '{"profile_id": "k197eg5j", "task_type": "page_probe"}' | python main.py --stdin
"""

import sys
import json
import argparse
import logging

sys.path.insert(0, ".")

from src.worker import TaskRunner, Task


def setup_logging(verbose: bool):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="Axon Browser Worker")
    parser.add_argument("task_json", nargs="?", help="Task as JSON string")
    parser.add_argument("--file", "-f", help="Read task from JSON file")
    parser.add_argument("--stdin", action="store_true", help="Read task from stdin")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose logging")
    parser.add_argument("--artifacts-dir", default="artifacts", help="Artifacts directory")

    args = parser.parse_args()
    setup_logging(args.verbose)

    # Get task JSON
    task_data = None

    if args.stdin:
        task_data = sys.stdin.read()
    elif args.file:
        with open(args.file) as f:
            task_data = f.read()
    elif args.task_json:
        task_data = args.task_json
    else:
        parser.print_help()
        sys.exit(1)

    # Parse and run
    try:
        task = Task.from_json(task_data)
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Invalid task JSON: {e}"}))
        sys.exit(1)

    runner = TaskRunner(artifacts_dir=args.artifacts_dir)
    result = runner.run(task)

    # Output result as JSON
    print(result.to_json())

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
