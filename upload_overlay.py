"""Upload the sample-data overlay files for a run to S3.

The instances clone the public GitHub repo on boot, then download THESE files
from s3://chrononet-checkpoints/bootstrap/<run_id>/ and layer them over the
clone. That is how the sample-data demo code reaches the instances without
changing the GitHub repo.

Usage (from the repo root, venv active, AWS credentials set):
    python upload_overlay.py --run-id run-laptop-20261116-120000
"""
import argparse
import os
import sys

import boto3

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
FILES = [
    "app/sample_data_generator.py",
    "app/sample_artifact.py",
    "app/main.py",
    "monitoring/instance_agent.py",
    "data_backend/aws/dynamodb_client.py",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True,
                    help="must match the --run-id you pass to launch_primary")
    args = ap.parse_args()
    s3 = boto3.client("s3", region_name="ap-south-1")
    for rel in FILES:
        src = os.path.join(REPO_ROOT, rel)
        if not os.path.exists(src):
            print(f"MISSING {src} - did you copy the patch files into the repo?")
            return 1
        key = f"bootstrap/{args.run_id}/{rel}"
        s3.upload_file(src, "chrononet-checkpoints", key)
        print(f"uploaded {rel} -> s3://chrononet-checkpoints/{key}")
    print("done. Next: python -m orchestration.launch_primary --run-id " + args.run_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
