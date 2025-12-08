#!/usr/bin/env python3
# run_all_channels.py
import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# These are channel slugs we found.
CHANNELS = ["p1", "p2", "p3", "p4aarhus",
            "p4bornholm", "p4esbjerg", "p4fyn",
            "p4kbh", "p4nord", "p4sjaelland", "p4syd",
            "p4trekanten", "p4vest", "p5", "p6beat", "p8jazz"]


def run(cmd: list[str]) -> int:
    return subprocess.run(cmd, check=False).returncode  # streams output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--stop-on-error", action="store_true")
    args = ap.parse_args()

    # validate date
    datetime.strptime(args.date, "%Y-%m-%d")

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    scraper = Path(__file__).with_name("dr_scraper.py")
    if not scraper.exists():
        print(
            f"ERROR: {scraper.name} not found next to this file.", file=sys.stderr)
        sys.exit(2)

    print(
        f"Running {scraper.name} for {len(CHANNELS)} channels on {args.date}\n")
    failures = []
    for i, ch in enumerate(CHANNELS, 1):
        out_path = data_dir / f"dr_{ch}_{args.date}.csv"
        cmd = [
            sys.executable,  # current Python interpreter
            "-u",            # unbuffered output
            str(scraper),
            "--channel", ch,
            "--date", args.date,
            "--out", str(out_path),
        ]
        print(f"[{i}/{len(CHANNELS)}] {ch} → {out_path}")
        rc = run(cmd)
        if rc != 0:
            print(f"  ❌ Failed ({rc})")
            failures.append(ch)
            if args.stop_on_error:
                break
        else:
            print("  ✅ Done")

    if failures:
        print(f"\nCompleted with failures in: {', '.join(failures)}")
        sys.exit(1)
    print("\nAll channels completed successfully.")


if __name__ == "__main__":
    main()
