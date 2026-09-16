"""Publish ChronoNet migration alerts to Amazon SNS.

Topic resolution (precedence, no invented ARNs):
  1. Env var CHRONONET_SNS_TOPIC_ARN  — explicit override (any topic/region)
  2. Derived from shared.constants.SNS_TOPIC_NAME
       arn:aws:sns:{AWS_REGION}:{caller_account}:chrononet-alerts

The topic already exists in the shared account. We never create it at runtime;
create_topic_if_missing + the --create-topic CLI exist only for bootstrapping
a brand-new account.

Publishing from the orchestrator is BEST-EFFORT: a failure to notify is logged
as a WARNING and never fails the migration (same philosophy as the checkpoint
S3 upload — local state first, remote side-effect best-effort).

Alert JSON shape (documented in shared/contracts.md #4):
  {
    "type": "migration_completed",
    "migration_id": "ISO8601 sort key",
    "run_id": "string",
    "from_vm_id": "string",
    "to_vm_id": "string",
    "status": "completed",
    "health_ok": true,
    "downtime_seconds": 1.5,
    "resumed_index": 20,
    "provision_market": "spot",
    "checkpoint_key": "checkpoints/run-1/...json",
    "region": "ap-south-1"
  }

CLI:
  python -m data_backend.aws.sns_client --service-info
  python -m data_backend.aws.sns_client --create-topic   # idempotent bootstrap
  python -m data_backend.aws.sns_client --test-alert     # real publish + verify
"""

import argparse
import json
import os
import sys

import boto3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import AWS_REGION, SNS_TOPIC_NAME  # noqa: E402


class SnsClient:
    """Thin wrapper around boto3 SNS for ChronoNet migration alerts."""

    def __init__(self, region: str | None = None, topic_arn: str | None = None):
        self.region = region or AWS_REGION
        self._sns = boto3.client("sns", region_name=self.region)
        self._sts = boto3.client("sts", region_name=self.region)
        self._topic_arn = topic_arn
        self._resolved_arn = None

    # ── topic resolution ────────────────────────────────────────────────────
    @property
    def topic_arn(self) -> str:
        """Resolve the topic ARN:
        1. explicit constructor value
        2. CHRONONET_SNS_TOPIC_ARN env var
        3. arn:aws:sns:{region}:{account}:{SNS_TOPIC_NAME}
        """
        if self._resolved_arn:
            return self._resolved_arn
        if self._topic_arn:
            self._resolved_arn = self._topic_arn
            return self._resolved_arn
        env = os.environ.get("CHRONONET_SNS_TOPIC_ARN", "").strip()
        if env:
            if not env.startswith("arn:aws:sns:"):
                raise ValueError(
                    f"CHRONONET_SNS_TOPIC_ARN is not an SNS ARN: {env!r}")
            self._resolved_arn = env
            return self._resolved_arn
        account = self._sts.get_caller_identity()["Account"]
        self._resolved_arn = f"arn:aws:sns:{self.region}:{account}:{SNS_TOPIC_NAME}"
        return self._resolved_arn

    def uses_default_topic(self) -> bool:
        """True when the ARN is derived (not overridden by env / constructor)."""
        return os.environ.get("CHRONONET_SNS_TOPIC_ARN") is None and self._topic_arn is None

    def describe_topic(self) -> dict:
        """Fetch topic attributes; raises sns.NotFoundException if absent."""
        return self._sns.get_topic_attributes(TopicArn=self.topic_arn)

    def create_topic_if_missing(self) -> tuple[str, bool]:
        """
        Idempotent bootstrap for a fresh account. Creates the derived topic
        (never the messaged env override) and returns (arn, created).
        """
        target = self.topic_arn
        try:
            self.describe_topic()
            return target, False
        except self._sns.exceptions.NotFoundException:
            if not self.uses_default_topic():
                raise PermissionError(
                    f"Topic {target} does not exist and it was supplied explicitly "
                    "(env/constructor) — create it in the AWS console.")
            resp = self._sns.create_topic(Name=SNS_TOPIC_NAME)
            arn = resp["TopicArn"]
            self._resolved_arn = arn
            return arn, True

    # ── publishing ──────────────────────────────────────────────────────────
    def publish_alert(
        self,
        alert: dict,
        subject: str | None = None,
        message_attributes: dict | None = None,
    ) -> dict:
        """Publish one alert payload to the topic. Returns the boto3 response."""
        subject = subject or "ChronoNet migration alert"
        kwargs = {
            "TopicArn": self.topic_arn,
            "Message": json.dumps(alert, indent=2, sort_keys=True, default=str),
            "Subject": subject,
        }
        if message_attributes:
            kwargs["MessageAttributes"] = message_attributes
        return self._sns.publish(**kwargs)

    def publish_migration_alert(self, result: dict) -> dict:
        """
        Build the contractual alert body (#4 in shared/contracts.md) from a
        recovery_flow.run_migration() result and publish it.
        """
        alert = {
            "type": "migration_completed",
            "migration_id": result.get("migration_id"),
            "run_id": result.get("run_id"),
            "from_vm_id": result.get("from_vm_id"),
            "to_vm_id": result.get("to_vm_id"),
            "status": result.get("status"),
            "health_ok": result.get("health_ok"),
            "downtime_seconds": result.get("downtime_seconds"),
            "resumed_index": result.get("resumed_index"),
            "provision_market": result.get("provision_market"),
            "checkpoint_key": result.get("checkpoint_key"),
            "region": self.region,
        }
        status = alert["status"]
        subject = (f"ChronoNet migration {status}: "
                   f"{alert.get('from_vm_id')} -> {alert.get('to_vm_id')} "
                   f"({alert.get('downtime_seconds')}s downtime)")
        subject = subject[:100]  # SNS subjects are limited to 100 chars
        return self.publish_alert(alert, subject=subject)


def main() -> int:
    parser = argparse.ArgumentParser(description="ChronoNet SNS alerting utilities")
    parser.add_argument("--service-info", action="store_true",
                        help="Resolve + report the SNS topic ARN in use.")
    parser.add_argument("--create-topic", action="store_true",
                        help="Idempotent bootstrap of the default topic for a fresh account.")
    parser.add_argument("--test-alert", action="store_true",
                        help="Publish one real alert with sample migration data and verify.")
    args = parser.parse_args()

    client = SnsClient()

    if args.service_info:
        arn = client.topic_arn
        print(f"[service-info] Topic ARN  : {arn}")
        print(f"[service-info] Region     : {client.region}")
        print(f"[service-info] Source     : {'env CHRONONET_SNS_TOPIC_ARN' if not client.uses_default_topic() else 'derived (constants.SNS_TOPIC_NAME + caller account)'}")
        try:
            attrs = client.describe_topic()
            print(f"[service-info] Exists     : yes ({attrs.get('Attributes', {}).get('DisplayName', 'no display name')})")
        except Exception as e:
            print(f"[service-info] Exists     : NO ({type(e).__name__}: {e})")
        return 0

    if args.create_topic:
        arn, created = client.create_topic_if_missing()
        print(f"[create-topic] {'created' if created else 'already exists'}: {arn}")
        return 0

    if args.test_alert:
        sample = {
            "run_id": "run-sns-test",
            "from_vm_id": "vm-sns-test-src",
            "to_vm_id": "vm-sns-test-dst",
            "migration_id": "2026-09-15T00:00:00+00:00",
            "status": "completed",
            "health_ok": True,
            "downtime_seconds": 1.5,
            "resumed_index": 12,
            "provision_market": "spot",
            "checkpoint_key": "checkpoints/run-sns-test/x.json",
        }
        try:
            client.describe_topic()
        except Exception as e:
            print(f"[test-alert] FAIL: topic unavailable ({type(e).__name__}: {e})")
            return 1
        try:
            resp = client.publish_migration_alert(sample)
        except Exception as e:
            print(f"[test-alert] FAIL: publish error — {type(e).__name__}: {e}")
            return 1
        msg_id = resp.get("MessageId")
        print(f"[test-alert] OK: published to {client.topic_arn}")
        print(f"[test-alert] OK: MessageId={msg_id}")
        print("[test-alert] Alert body sent:")
        print(json.dumps(sample, indent=2, sort_keys=True))
        return 0 if msg_id else 1

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())