# DynamoDB Table Schemas

All tables live in `ap-south-1`, use `PAY_PER_REQUEST` billing, and their names
are defined once in `shared/constants.py`.

> Alignment note: the tables below already exist in the shared account with
> these key shapes. `create_tables.py` is idempotent against them, and
> `aws/dynamodb_client.py` is written to match them exactly. The vm-state table
> is keyed by `instance_id` (the EC2 instance / our `vm_id`); `run_id` is a
> regular attribute because a run migrates across instances.

## chrononet-vm-state
One row per VM instance — that instance's current/latest state and checkpoint
progress while it hosted the run.

| Key          | Attribute | Type |
|--------------|-----------|------|
| HASH         | instance_id           | S | EC2 instance id (== vm_id)
| attribute    | vm_id                 | S | contract-facing alias of instance_id
| attribute    | run_id                | S |
| attribute    | region                | S |
| attribute    | status                | S | running / migrating / terminated
| attribute    | cpu_percent           | N |
| attribute    | ram_percent           | N |
| attribute    | risk_percent          | N |
| attribute    | migration_count       | N |
| attribute    | last_downtime_seconds | N |
| attribute    | last_processed_index    | N | checkpoint tracking
| attribute    | last_checkpoint_timestamp | S | checkpoint tracking (ISO8601)
| attribute    | last_checkpoint_key     | S | checkpoint tracking (S3 object key)
| attribute    | updated_at            | S | ISO8601

## chrononet-migrations
One row per migration event per run, enabling migration history (`/history`).

| Key          | Attribute | Type |
|--------------|-----------|------|
| HASH         | run_id          | S | constant across migrations
| SORT (RANGE) | timestamp       | S | ISO8601 (sortable; microsecond precision)
| attribute    | from_vm_id      | S |
| attribute    | to_vm_id        | S |
| attribute    | triggered_by    | S | imds / prediction
| attribute    | risk_percent    | N |
| attribute    | downtime_seconds | N |
| attribute    | status          | S | started / completed / failed
| attribute    | checkpoint_key  | S | S3 key the new instance resumes from
| attribute    | completed_at    | S | ISO8601 (optional, set via complete_migration)