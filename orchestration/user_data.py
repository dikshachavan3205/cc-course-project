"""EC2 bootstrap (user-data) for a ChronoNet workload instance.

On boot the instance: schedules a safety shutdown, reads its own identity from
IMDSv2, installs git/python/boto3, clones the repo, and starts app/main.py with
CHRONONET_RESTORE_FROM_S3=true so it resumes from the latest S3 checkpoint.

NOTE: the instance clones the PUBLIC GitHub repo, so push your code to `main`
before launching. Run parameters are stored in S3 (runs/<run_id>/config.json)
so a replacement instance is started with the same settings as the original.
"""
import json
import shlex

import boto3

from shared.constants import AWS_REGION, S3_CHECKPOINT_BUCKET

DEFAULT_REPO_URL = "https://github.com/dikshachavan3205/cc-course-project.git"
DEFAULT_CONFIG = {
    "repo_url": DEFAULT_REPO_URL,
    "repo_ref": "main",
    "total_steps": 2000,
    "step_delay": 0.5,
    "checkpoint_interval": 10,
    "ttl_minutes": 180,
}

_TEMPLATE = r"""#!/bin/bash
exec > >(tee -a /var/log/chrononet-bootstrap.log) 2>&1
echo "[bootstrap] start $(date -u +%FT%TZ)"

# Safety net: terminate this instance after the TTL no matter what.
shutdown -h +@@TTL@@ "ChronoNet safety shutdown"

TOKEN=$(curl -s -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 21600")
imds() { curl -s -H "X-aws-ec2-metadata-token: $TOKEN" "http://169.254.169.254/latest/meta-data/$1"; }
INSTANCE_ID=$(imds instance-id)
INSTANCE_TYPE=$(imds instance-type)
LIFECYCLE=$(imds instance-life-cycle)
if [ "$LIFECYCLE" = "spot" ]; then MARKET=spot; else MARKET=ondemand; fi
echo "[bootstrap] $INSTANCE_ID $INSTANCE_TYPE $MARKET"

for i in 1 2 3; do dnf install -y git python3-pip && break; sleep 5; done
for i in 1 2 3; do python3 -m pip install boto3 psutil && break; sleep 5; done
for i in 1 2 3; do git clone --depth 1 --branch @@REF@@ @@REPO@@ /opt/chrononet && break; sleep 5; done

# Sample-data overlay: pull this run's patched files from S3 and layer them
# onto the cloned repo before anything starts.
cat > /tmp/chrononet_overlay.py <<'PYEOF'
import boto3
s3 = boto3.client("s3", region_name="@@REGION@@")
FILES = [
    "app/sample_data_generator.py",
    "app/sample_artifact.py",
    "app/main.py",
    "monitoring/instance_agent.py",
    "data_backend/aws/dynamodb_client.py",
]
for rel in FILES:
    s3.download_file("@@BUCKET@@", f"bootstrap/@@RUN_ID@@/{rel}", f"/opt/chrononet/{rel}")
print("[overlay] sample-data files applied")
PYEOF
for i in 1 2 3 4 5; do python3 /tmp/chrononet_overlay.py && break; sleep 10; done

cat > /etc/chrononet.env <<EOF
CHRONONET_RUN_ID=@@RUN_ID@@
CHRONONET_VM_ID=$INSTANCE_ID
CHRONONET_INSTANCE_TYPE=$INSTANCE_TYPE
CHRONONET_MARKET=$MARKET
CHRONONET_RESTORE_FROM_S3=true
CHRONONET_REGISTER_STATE=true
CHRONONET_TOTAL_STEPS=@@STEPS@@
CHRONONET_STEP_DELAY=@@DELAY@@
CHRONONET_CHECKPOINT_INTERVAL=@@INTERVAL@@
EOF

set -a; . /etc/chrononet.env; set +a
cd /opt/chrononet
nohup python3 app/main.py > /var/log/chrononet-workload.log 2>&1 &
echo "[bootstrap] workload started pid $! at $(date -u +%FT%TZ)"
nohup python3 monitoring/instance_agent.py > /var/log/chrononet-agent.log 2>&1 &
"""


def build_user_data(*, run_id: str, repo_url: str = DEFAULT_CONFIG["repo_url"],
                    repo_ref: str = DEFAULT_CONFIG["repo_ref"],
                    total_steps: int = DEFAULT_CONFIG["total_steps"],
                    step_delay: float = DEFAULT_CONFIG["step_delay"],
                    checkpoint_interval: int = DEFAULT_CONFIG["checkpoint_interval"],
                    ttl_minutes: int = DEFAULT_CONFIG["ttl_minutes"]) -> str:
    return (_TEMPLATE
            .replace("@@TTL@@", str(int(ttl_minutes)))
            .replace("@@REF@@", shlex.quote(repo_ref))
            .replace("@@REPO@@", shlex.quote(repo_url))
            .replace("@@RUN_ID@@", shlex.quote(run_id))
            .replace("@@REGION@@", AWS_REGION)
            .replace("@@BUCKET@@", S3_CHECKPOINT_BUCKET)
            .replace("@@STEPS@@", str(int(total_steps)))
            .replace("@@DELAY@@", str(float(step_delay)))
            .replace("@@INTERVAL@@", str(int(checkpoint_interval))))


def _config_key(run_id: str) -> str:
    return f"runs/{run_id}/config.json"


def save_run_config(run_id: str, cfg: dict) -> None:
    boto3.client("s3", region_name=AWS_REGION).put_object(
        Bucket=S3_CHECKPOINT_BUCKET, Key=_config_key(run_id),
        Body=json.dumps(cfg), ContentType="application/json")


def load_run_config(run_id: str) -> dict:
    """Stored launch parameters for a run; {} (=> defaults) if none/unreadable."""
    try:
        obj = boto3.client("s3", region_name=AWS_REGION).get_object(
            Bucket=S3_CHECKPOINT_BUCKET, Key=_config_key(run_id))
        cfg = json.loads(obj["Body"].read().decode("utf-8"))
        return {k: v for k, v in cfg.items() if k in DEFAULT_CONFIG}
    except Exception:  # noqa: BLE001
        return {}
