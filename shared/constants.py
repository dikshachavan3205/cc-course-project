"""Shared constants: bucket names, table names, thresholds."""

RISK_THRESHOLD = 0.8
S3_CHECKPOINT_BUCKET = "chrononet-checkpoints"
DYNAMODB_TABLE_VM_STATE = "chrononet-vm-state"
DYNAMODB_TABLE_MIGRATIONS = "chrononet-migrations"

AWS_REGION = "ap-south-1"          # set to your team's actual region

RISK_THRESHOLD_WARN = 0.5          # optional: earlier "elevated risk" warning for dashboard

S3_CHECKPOINT_PREFIX = "checkpoints"                # key pattern: checkpoints/{run_id}/{timestamp}.json

DYNAMODB_TABLE_PREDICTIONS = "chrononet-predictions"  # optional: log every risk score, not just migrations

SNS_TOPIC_NAME = "chrononet-alerts"

# IAM instance profile attached to every launched replacement instance
# (grants S3/DynamoDB/SNS permissions via the chrononet-ec2-role policy).
INSTANCE_PROFILE = "chrononet-ec2-role"

CHECKPOINT_INTERVAL_SECONDS = 60
IMDS_POLL_INTERVAL_SECONDS = 5
METRICS_POLL_INTERVAL_SECONDS = 15
DASHBOARD_POLL_INTERVAL_SECONDS = 5

INSTANCE_TYPE = "t3.micro"

AWS_REGION = "ap-south-1"