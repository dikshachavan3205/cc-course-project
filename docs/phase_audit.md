# ChronoNet Phase Audit — status summary

Audit run against live AWS (account 511131039673, region ap-south-1).
Rule: one phase at a time; `✅ WORKING` = verified as-built, `⚠️ FIXED` = code change
was required, `❌ BLOCKED` = cannot complete without an external dependency.

## Phase status

| Phase | Status | Notes |
|---|---|---|
| 0 — Environment | ⚠️ FIXED | numpy added to prediction reqs; stale `requests` dropped; `.env.example` aligned to `CHRONONET_*` vars; regenerable dataset dirs gitignored |
| 1 — IAM | ⚠️ FIXED (visibility closed) | role `chrononet-ec2-role` + profile exist, trusts EC2 only; zero hardcoded keys. **Attached policies are 4 AWS-managed**: `CloudWatchReadOnlyAccess`, `AmazonSNSFullAccess`, `AmazonDynamoDBFullAccess`, `AmazonS3FullAccess` — services within the S3/DDB/CloudWatch/SNS set (EC2/EventBridge correctly absent from an instance role), **but broader than the repo's resource-scoped design**; the attached set is not the custom `ec2_role_policy.json` |
| 2 — Dataset | ✅ WORKING | real fetchers (2,536 price rows, 34 regions / 1,155 types); 400-row dataset clean (0 NaN/neg/dupe); seed-42 split; retrain MAE 0.0207 / R² 0.8828 |
| 3 — Docker | ✅ WORKING | build 258MB; run-to-completion; volume-persisted resume confirmed at step 17 |
| 4 — S3 Checkpoints | ✅ WORKING | key pattern `checkpoints/{run_id}/{timestamp}.json`; load-latest verified; stale `{vm_id}` comment fixed. **No lifecycle rule** (optional) |
| 5 — Monitoring | ⚠️ FIXED → ✅ WORKING | `cloudwatch_collector` stub implemented (real CPU, explicit-None RAM); imds_watcher IMDSv2 verified **on a live instance**; **EventBridge rule deployed for real (below)** |
| 6 — Model | ⚠️ FIXED | strict (0,1) risk clamp; only shared `RISK_THRESHOLD`; MAE 0.0207 / R² 0.8828 vs target |
| 7 — DynamoDB | ✅ WORKING | live self-check; field names/types match contracts; history filters + sorts by run |
| 8 — Orchestration | ⚠️ FIXED | profile attach + idempotent terminate; Spot→On-Demand fallback; `test-migration` honors `--provision`. **Real EC2 E2E passed** (below) |
| 9 — SNS | ✅ WORKING | ARN derived, not hardcoded; subscription confirmed; test alert delivered |
| 10 — API | ⚠️ FIXED | added `GET /checkpoint-status`; shapes + empty cases verified; CORS `*` |
| 11 — Dashboard | ⚠️ FIXED | poll default aligned to `DASHBOARD_POLL_INTERVAL_SECONDS=5`; live `/status` + `/history` polling; labels verified; build clean |

## Real EC2 E2E (Phase 8) — PASSED, downtime measured

Run id `run-e2e-real`, t3.micro, AMI `ami-0ee11497c4eac651d`, subnet
`subnet-02ed9018ca236ff1a`, instance profile `chrononet-ec2-role`.

1. Launched via `launch_instance.provision_instance` (Spot). Instance `i-0669a3f5474513ba2`
   reached `running`; profile attached; on-instance user-data (IMDSv2 token → instance-id)
   booted the real workload (`app/main.py`), which checkpointed to S3 every 5 s.
2. `recovery_flow.run_migration(..., provision_mode="real")` executed against the live instance:
   - step 2 forced checkpoint → S3 (hub local index 2)
   - step 4 provisioned replacement **Spot** instance `i-0f9c1e24f72a89e74`
   - step 5 downloaded the latest S3 checkpoint → **resumed_index 30027** (real instance
     progress, not 0, not the hub's forced 2)
   - step 7 terminated the original instance; SNS alert published to `chrononet-alerts`
3. **Downtime: 6.906 s** (trigger receipt → step-6 resume complete).
4. All instances terminated afterwards; account-wide `running,pending` check returned `[]`.

### Bug found + fixed by the real test
`load_latest_checkpoint_from_s3` picked the lexicographically max key under the run prefix
and blindly `json.loads`ed it. A non-checkpoint artifact (probe logs under the same prefix)
crashed step 5 with `JSONDecodeError`. Fixed by filtering to `*.json` keys only.

## Phase 5 live-instance checks — PASSED

On the same live instance (before termination):
- `monitoring/imds_watcher --once` (IMDSv2, normal conditions): **no notice detected**
  (exit 0, no WARNING) — "No interruption notice detected." on stderr.
- `monitoring/cloudwatch_collector` for `i-0669a3f5474513ba2`: **real CPUUtilization 0.68%**
  returned over 8-min window (RAM stays explicit `None` by design).

## EventBridge rule — deployed for real

`chrononet-spot-interruption-rule` (created from `monitoring/eventbridge_setup/rule_definition.json`):
- State **ENABLED**; EventPattern `source=["aws.ec2"]`, `detail-type=["EC2 Spot Instance Interruption Warning"]`.
- Target: `chrononet-alerts-sns` → `arn:aws:sns:ap-south-1:511131039673:chrononet-alerts` (PutTargets: 0 failures).
- SNS topic policy: added `EventBridgePublishToSNS` statement (`Principal: events.amazonaws.com`, `sns:Publish`, scoped via `AWS:SourceArn` = the rule ARN), preserving the existing default statement.
- Verified via `events:describe-rule` (ENABLED) and `events:list-targets-by-rule` (correct target ARN).

## Needs-input / gaps
- **Replace broad managed policies on `chrononet-ec2-role`** before any go-live: currently `AmazonS3FullAccess` / `AmazonDynamoDBFullAccess` / `AmazonSNSFullAccess` / `CloudWatchReadOnlyAccess` — world-scoped, not the resource-scoped least-privilege policy the design intends. The repo's `ec2_role_policy.json` is the **hub-operator** policy (ec2 run/terminate + scoped S3/DDB/SNS), not an instance-scoped policy; decide on the swap (author an instance-scoped policy vs. accept managed policies).
- Live `metrics_buffer.py` / `prediction/evaluate.py` remain one-line stubs (out of checklist scope).
- `AWS_REGION` defined twice in `shared/constants.py` (harmless); `README.md` stale ("Phase 1 complete").
- Windows WDAC blocks newest ML wheels → pinned pandas 2.2.3 / sklearn 1.4.2 / xgboost 2.0.3 in `venv/`.