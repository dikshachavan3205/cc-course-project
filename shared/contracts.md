# Shared Contracts

Agree on these 3 formats BEFORE writing integration code:

## 1. Checkpoint JSON (written to S3)
```json
{
  "vm_id": "string",
  "last_processed_index": 0,
  "timestamp": "ISO8601"
}
```

## 2. API response shape (GET /status)
```json
{
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
  "vm_id": "string",
  "risk_percent": 0,
  "threshold_exceeded": false,
  "timestamp": "ISO8601"
}
```
