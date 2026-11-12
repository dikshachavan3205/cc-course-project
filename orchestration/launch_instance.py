"""boto3: provision a replacement EC2 instance — Spot first, On-Demand fallback.

Real provisioning is DESTRUCTIVE/COSTLY, so it is gated behind
CHRONONET_ALLOW_REAL_EC2=true (see provision_instance). The orchestrator's
default mode is `simulate` (no AWS EC2 calls) which is what the CLI test uses.

Real flow:
  1. request a Spot instance (InstanceMarketOptions: Spot)
  2. if Spot call fails (e.g. InsufficientInstanceCapacity / RequestLimitExceeded)
     -> gracefully fall back to On-Demand (plain run_instances)
  3. wait until the instance is running
"""

import base64
import os
import sys

import boto3

# Make `shared/` importable whether run as `-m orchestration.launch_instance`
# (repo root on sys.path) or `python orchestration/launch_instance.py`.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import INSTANCE_PROFILE  # noqa: E402


def _fake_instance_id(prefix: str = "i") -> str:
    """Deterministic-looking fake id so simulate mode needs no randomness."""
    import hashlib

    seed = os.environ.get("CHRONONET_RUN_ID", "run")
    digest = hashlib.sha1(seed.encode()).hexdigest()[:12]
    return f"{prefix}-{digest}"


def simulate_provision(instance_type: str, logger=None) -> dict:
    """Simulate provisioning a Spot instance — no AWS calls, no cost."""
    reservation = {
        "mode": "simulate",
        "market": "spot",               # assumed to have won Spot capacity
        "instance_id": _fake_instance_id(),
        "instance_type": instance_type,
        "status": "running",
    }
    if logger:
        logger.note("sim-provision", **reservation)
    return reservation


def provision_instance(
    *,
    region: str,
    instance_type: str,
    image_id: str | None = None,
    subnet_id: str | None = None,
    key_name: str | None = None,
    security_group_ids: list[str] | None = None,
    instance_profile: str | None = INSTANCE_PROFILE,
    user_data: str | None = None,
    tags: dict | None = None,
    logger=None,
    allow_real: bool = False,
) -> dict:
    """
    Provision a replacement instance via boto3.

    Spot is attempted FIRST; if the Spot request fails, we fall back to
    On-Demand (graceful degradation documented in the timeline).

    Raises PermissionError unless allow_real=True (i.e. the operator opted in).
    Raises ValueError if image_id is missing (required for a real launch).
    """
    if not allow_real:
        raise PermissionError(
            "Real EC2 provisioning is disabled. Set CHRONONET_ALLOW_REAL_EC2=true "
            "to opt in (costs money / creates real resources)."
        )
    if not image_id:
        raise ValueError(
            "Real provisioning requires an AMI: set CHRONONET_AMI "
            "(plus optionally CHRONONET_SUBNET_ID / CHRONONET_KEY_NAME / "
            "CHRONONET_SECURITY_GROUP_IDS)."
        )

    ec2 = boto3.client("ec2", region_name=region)

    base_kwargs = {
        "ImageId": image_id,
        "InstanceType": instance_type,
        "MinCount": 1,
        "MaxCount": 1,
    }
    if subnet_id:
        base_kwargs["SubnetId"] = subnet_id
    if key_name:
        base_kwargs["KeyName"] = key_name
    if security_group_ids:
        base_kwargs["SecurityGroupIds"] = security_group_ids
    if instance_profile:
        # Attach the chrononet-ec2-role IAM instance profile so the launched
        # instance can itself write checkpoints to S3, read/write DynamoDB and
        # publish SNS alerts. Pass instance_profile=None to launch without one.
        base_kwargs["IamInstanceProfile"] = {"Name": instance_profile}
    # Instance-initiated shutdown (the bootstrap's safety timer) must TERMINATE,
    # not stop, so a forgotten instance never lingers (also covers On-Demand fallback).
    base_kwargs["InstanceInitiatedShutdownBehavior"] = "terminate"
    base_kwargs["MetadataOptions"] = {"HttpTokens": "required", "HttpEndpoint": "enabled"}  # IMDSv2
    if tags:
        base_kwargs["TagSpecifications"] = [{
            "ResourceType": "instance",
            "Tags": [{"Key": k, "Value": str(v)} for k, v in tags.items()],
        }]
    if user_data:
        # Pass RAW text: botocore base64-encodes UserData itself. Encoding here too
        # would double-encode it and cloud-init would never run the script.
        base_kwargs["UserData"] = user_data

    # ── Attempt 1: Spot ──
    response = None
    try:
        response = ec2.run_instances(
            **base_kwargs,
            InstanceMarketOptions={
                "MarketType": "spot",
                "SpotOptions": {
                    "SpotInstanceType": "one-time",
                    "InstanceInterruptionBehavior": "terminate",
                },
            },
        )
        market = "spot"
        if logger:
            logger.note("provision-attempt", market="spot", result="ok")
    except Exception as exc:  # noqa: BLE001 - logged, then fall back
        if logger:
            logger.note("provision-attempt", market="spot",
                        result="failed", reason=f"{type(exc).__name__}: {exc}")
        # ── Attempt 2: graceful On-Demand fallback ──
        response = ec2.run_instances(**base_kwargs)
        market = "ondemand-fallback"
        if logger:
            logger.note("provision-attempt", market="ondemand-fallback", result="ok")

    instance_id = response["Instances"][0]["InstanceId"]

    ec2.get_waiter("instance_running").wait(
        InstanceIds=[instance_id],
        WaiterConfig={"Delay": 2, "MaxAttempts": 60},
    )

    return {
        "mode": "real",
        "market": market,
        "instance_id": instance_id,
        "instance_type": instance_type,
        "status": "running",
    }


def pick_replacement_pool(*, region: str, old_instance_id: str, subnet_ids: list,
                          instance_types: list, logger=None) -> tuple:
    """
    Choose (subnet_id, instance_type) for a replacement, preferring a DIFFERENT
    availability zone and instance type than the instance being replaced: a
    reclaimed Spot pool (type + AZ) is the likeliest to be reclaimed again.
    Falls back to the first configured option when nothing differs.
    """
    ec2 = boto3.client("ec2", region_name=region)
    old_az = old_type = None
    try:
        inst = ec2.describe_instances(InstanceIds=[old_instance_id])["Reservations"][0]["Instances"][0]
        old_az, old_type = inst["Placement"]["AvailabilityZone"], inst["InstanceType"]
    except Exception:  # noqa: BLE001 - old instance unknown/gone: no preference
        pass

    subnet_az = {}
    if subnet_ids:
        for sn in ec2.describe_subnets(SubnetIds=subnet_ids)["Subnets"]:
            subnet_az[sn["SubnetId"]] = sn["AvailabilityZone"]
    subnet = next((s for s in subnet_ids if subnet_az.get(s) != old_az), None) or (subnet_ids[0] if subnet_ids else None)
    itype = next((t for t in instance_types if t != old_type), None) or instance_types[0]

    if logger:
        logger.note("pool-selected", old_az=old_az, old_type=old_type,
                    new_az=subnet_az.get(subnet), new_type=itype, subnet_id=subnet)
    return subnet, itype
