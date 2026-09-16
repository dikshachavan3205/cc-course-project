# IAM Role Setup Notes

The migration orchestrator (`orchestration/recovery_flow.py` + the boto3
helpers in `orchestration/launch_instance.py` and `orchestration/terminate_instance.py`)
needs a role/permissions covering three areas:

## 1. Instance provisioning (EC2)
- `ec2:RunInstances` to launch the replacement instance
- `ec2:RequestSpotInstances` — the Spot-first attempt
- `ec2:DescribeInstanceStatus` / `ec2:DescribeInstances` for the running waiter
- `ec2:TerminateInstances` to kill the old VM after a successful migration

## 2. Checkpoint durability (S3)
- `s3:PutObject` / `s3:GetObject` / `s3:ListBucket` / `s3:DeleteObject`
  on `chrononet-checkpoints` — see `shared/constants.py` (bucket and prefix
  must match exactly; do NOT invent names).

## 3. State + migration history (DynamoDB)
- `dynamodb:PutItem` / `GetItem` / `UpdateItem` / `DeleteItem` / `Query`
  on the live tables `chrononet-vm-state` (HASH `instance_id`) and
  `chrononet-migrations` (HASH `run_id` + SORT `timestamp`).

## 4. Migration alerts (SNS)
- `sns:Publish` (and `sns:GetTopicAttributes` for the service-info check) on
  the topic `chrononet-alerts` — published by
  `data_backend/aws/sns_client.py` after every successful migration.

The exact JSON is in `ec2_role_policy.json`. Attach it to the instance role
via the AWS console (IAM → Roles → your instance role → Add permissions →
Create inline policy → paste JSON).

### Alternative for this repo
The local dev/test harness runs from `arn:aws:iam::511131039673:user/chrononet-shweta`
(keys in `C:\Users\HP\.aws\credentials`). That IAM user must itself hold the
ec2/s3/dynamodb permissions above for `--test-migration` (real-S3, real-DDB,
simulated EC2) to work.