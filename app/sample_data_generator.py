"""Sample data generator - the VISIBLE artifact ChronoNet carries across Spot migrations.

Every checkpoint cycle the workload runs this script once and appends its
one-line output to sample_data/sample_output.log. Both this script and the
cumulative log are uploaded into the run's S3 checkpoint folder and restored
onto the replacement instance after a migration - so you can SEE the same data
follow the job from one Spot instance to the next.

Run it by hand on any instance:  python3 app/sample_data_generator.py
"""
import os
import sys
from datetime import datetime, timezone


def main() -> None:
    step = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    checksum = (sys.argv[2] if len(sys.argv) > 2 else "no-checksum")[:12]
    vm = os.environ.get("CHRONONET_VM_ID", "unknown-vm")
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    print(f"step={step} | vm={vm} | checksum={checksum} | generated_at={ts} "
          f"| sample_payload=chrononet-demo-row-{step}")


if __name__ == "__main__":
    main()
