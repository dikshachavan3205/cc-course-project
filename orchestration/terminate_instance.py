"""boto3: terminate the old EC2 instance after a successful migration."""

import boto3
from botocore.exceptions import ClientError


def terminate_instance(*, region: str, instance_id: str, logger=None) -> dict:
    """
    Terminate an EC2 instance by id. Returns the terminating-instance record.

    Idempotent: an already-terminated or nonexistent instance is NOT an error —
    it is reported as `current_state: already-terminated` so the recovery flow
    never crashes on re-terminate/unknown ids. Any other AWS error propagates.
    """
    ec2 = boto3.client("ec2", region_name=region)
    try:
        response = ec2.terminate_instances(InstanceIds=[instance_id])
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {
            "InvalidInstanceID.NotFound",
            "InvalidInstanceID.Malformed",
            "IncorrectInstanceState",
        }:
            record = {
                "InstanceId": instance_id,
                "PreviousState": {"Name": "unknown"},
                "CurrentState": {"Name": "already-terminated"},
                "error": code,
            }
            if logger:
                logger.note("terminate", instance_id=instance_id,
                            prev="unknown", next="already-terminated", reason=code)
            return record
        raise
    record = response["TerminatingInstances"][0]
    if logger:
        logger.note(
            "terminate",
            instance_id=instance_id,
            prev=record["PreviousState"]["Name"],
            next=record["CurrentState"]["Name"],
        )
    return record


def simulate_terminate(instance_id: str, logger=None) -> dict:
    """Simulate termination — no AWS calls (used by --test-migration)."""
    record = {
        "InstanceId": instance_id,
        "PreviousState": {"Name": "running"},
        "CurrentState": {"Name": "terminated"},
    }
    if logger:
        logger.note("terminate", instance_id=instance_id,
                    prev="running", next="terminated", mode="simulate")
    return record