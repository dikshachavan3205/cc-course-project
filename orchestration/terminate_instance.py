"""boto3: terminate the old EC2 instance after a successful migration."""

import boto3


def terminate_instance(*, region: str, instance_id: str, logger=None) -> dict:
    """Terminate an EC2 instance by id. Returns the terminating-instance record."""
    ec2 = boto3.client("ec2", region_name=region)
    response = ec2.terminate_instances(InstanceIds=[instance_id])
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