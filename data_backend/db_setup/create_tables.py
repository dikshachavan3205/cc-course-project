"""Create the ChronoNet DynamoDB tables in ap-south-1 if they don't exist yet.

Table names come from shared/constants.py (single source of truth) — never
hardcode a table name in this repo.

  chrononet-vm-state     HASH key: instance_id  (one row per VM instance)
  chrononet-migrations   HASH key: run_id
                         SORT key: timestamp    (ISO8601, one row per migration)

NOTE: these key shapes match the tables already provisioned in the shared
account, so this script is idempotent against production.

Both tables use on-demand billing (PAY_PER_REQUEST) so there are no capacity
provisioning decisions for a student project.

Usage:
  python -m data_backend.db_setup.create_tables
"""

import os
import sys

import boto3

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from shared.constants import (  # noqa: E402
    AWS_REGION,
    DYNAMODB_TABLE_VM_STATE,
    DYNAMODB_TABLE_MIGRATIONS,
)

# v-- Single description of every table we own. Keyed by the CONSTANT, not a
# hardcoded string, so names can only change in one place.
TABLE_SCHEMAS = {
    DYNAMODB_TABLE_VM_STATE: {
        "KeySchema": [
            {"AttributeName": "instance_id", "KeyType": "HASH"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "instance_id", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
    DYNAMODB_TABLE_MIGRATIONS: {
        "KeySchema": [
            {"AttributeName": "run_id", "KeyType": "HASH"},
            {"AttributeName": "timestamp", "KeyType": "RANGE"},
        ],
        "AttributeDefinitions": [
            {"AttributeName": "run_id", "AttributeType": "S"},
            {"AttributeName": "timestamp", "AttributeType": "S"},
        ],
        "BillingMode": "PAY_PER_REQUEST",
    },
}


def create_table_if_missing(client, table_name: str) -> bool:
    """
    Creates a single table if it doesn't already exist. Blocks until the
    table reaches ACTIVE status. Returns True if created, False if it already
    existed.
    """
    try:
        client.describe_table(TableName=table_name)
        print(f"[db_setup] Table '{table_name}' already exists.")
        return False
    except client.exceptions.ResourceNotFoundException:
        pass  # safe to create

    print(f"[db_setup] Creating table '{table_name}' ...")
    client.create_table(TableName=table_name, **TABLE_SCHEMAS[table_name])

    client.get_waiter("table_exists").wait(TableName=table_name)
    print(f"[db_setup] Table '{table_name}' is ACTIVE.")
    return True


def create_tables_if_missing(client=None) -> list[str]:
    """
    Ensures every table in TABLE_SCHEMAS exists. Returns the list of table
    names that were actually created (empty if all already existed).
    """
    client = client or boto3.client("dynamodb", region_name=AWS_REGION)

    created = []
    for table_name in TABLE_SCHEMAS:
        if create_table_if_missing(client, table_name):
            created.append(table_name)
    return created


if __name__ == "__main__":
    try:
        created_tables = create_tables_if_missing()
    except Exception as e:
        print(f"[db_setup] ERROR: could not create tables: {type(e).__name__}: {e}")
        sys.exit(1)

    if created_tables:
        print(f"[db_setup] Created: {', '.join(created_tables)}")
    else:
        print("[db_setup] All ChronoNet tables already exist. Nothing to do.")
    print(f"[db_setup] Region: {AWS_REGION}")