## 1. Checkpoint JSON (written to S3)
```json
{
  "run_id": "string",
  "vm_id": "string",
  "last_processed_index": 0,
  "timestamp": "ISO8601"
}
```

## 2. API response shape (GET /status)
```json
{
  "run_id": "string",
  "vm_id": "string",
  "region": "string",
  "cpu_percent": 0,
  "ram_percent": 0,
  "risk_percent": 0,
  "migration_count": 0,
  "last_downtime_seconds": 0
}
```

## 3. Risk event JSON (Predictor -> Orchestrator)
```json
{
  "run_id": "string",
  "vm_id": "string",
  "risk_percent": 0,
  "threshold_exceeded": false,
  "timestamp": "ISO8601"
}
```

## 4. SNS alert JSON (published to chrononet-alerts on migration completion)
```json
{
  "type": "migration_completed",
  "migration_id": "string",
  "run_id": "string",
  "from_vm_id": "string",
  "to_vm_id": "string",
  "status": "completed",
  "health_ok": true,
  "downtime_seconds": 1.5,
  "resumed_index": 20,
  "provision_market": "spot",
  "checkpoint_key": "string",
  "region": "ap-south-1"
}
```


## 5. Checkpoint `state` (optional field, added to shape #1)
```json
"state": { "processed_count": 0, "checksum": "hex-string" }
```
Absent in old checkpoints; readers must tolerate a missing `state`.

## 6. chrononet-vm-state: new attributes (written by the on-instance agent)
`instance_type` (S), `market` (S: spot|ondemand), `network_mbps` (N),
`instance_age_minutes` (N), `interruption_notice` (BOOL), `resumed_index` (N),
`launched_at` (S, ISO8601). Existing fields unchanged.

## 7. chrononet-predictions (new table)
HASH `run_id` (S), SORT `timestamp` (S, ISO8601)
Attributes: `instance_id`, `instance_type`, `risk_percent` (N),
`cpu_percent`, `ram_percent`, `network_mbps`, `instance_age_minutes`,
`price_volatility`, `price_trend_ratio`, `savings_percent` (all N),
`threshold_migrate` (N), `source` (S: model|imds)

## 8. New API endpoints
- `GET /predictions?run_id=` -> `{run_id, predictions: [...newest first]}`
- `GET /instances?run_id=` -> `{run_id, instances: [{instance_id, status, instance_type, market, launched_at}]}`
- `GET /config` -> `{risk_warn_percent, risk_migrate_percent, provision_mode, checkpoint_interval_s}`

## 9. Environment variables
`CHRONONET_PROVISION_MODE` (simulate|real, default simulate),
`CHRONONET_ALLOW_REAL_EC2`, `CHRONONET_AMI`, `CHRONONET_SUBNET_ID`,
`CHRONONET_SECURITY_GROUP_IDS`, `CHRONONET_KEY_NAME` (optional),
`CHRONONET_RUN_ID`, `CHRONONET_VM_ID`, `CHRONONET_CHECKPOINT_INTERVAL`

## 10. Resource tags on every launched instance
`Project=chrononet`, `RunId=<run_id>`, `Role=workload`
