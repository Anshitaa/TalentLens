"""
Kafka topic definitions for TalentLens.

Topic              Partitions  Retention    Purpose
------------------ ----------  -----------  ----------------------------------------
employee-events         6      7 days       HR events: hire, terminate, promote, etc.
risk-score-updates      3      3 days       Risk score deltas after model inference
audit-log               3      30 days      Immutable log of every model decision
hiring-funnel-events    3      7 days       Candidate stage transitions
"""

KAFKA_TOPICS = {
    "employee-events": {
        "partitions": 6,
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,       # 7 days
        "description": "Raw HR events from HRIS system",
        "consumer_groups": [
            "risk-engine-consumer",   # exactly-once: triggers model inference
            "dashboard-consumer",     # at-most-once: WebSocket push
            "audit-consumer",         # at-least-once: S3 audit trail
        ],
    },
    "risk-score-updates": {
        "partitions": 3,
        "replication_factor": 1,
        "retention_ms": 3 * 24 * 60 * 60 * 1000,       # 3 days
        "description": "Computed risk score deltas after each inference run",
        "consumer_groups": ["dashboard-consumer"],
    },
    "audit-log": {
        "partitions": 3,
        "replication_factor": 1,
        "retention_ms": 30 * 24 * 60 * 60 * 1000,      # 30 days
        "description": "Immutable log of model decisions and HITL overrides",
        "consumer_groups": ["audit-consumer"],
    },
    "hiring-funnel-events": {
        "partitions": 3,
        "replication_factor": 1,
        "retention_ms": 7 * 24 * 60 * 60 * 1000,       # 7 days
        "description": "Application → screen → interview → offer → hire/reject",
        "consumer_groups": ["dashboard-consumer"],
    },
}

# Event schema versions — bump when payload shape changes
EVENT_SCHEMA_VERSION = "1.0"

# Partition key functions — determines which partition a message lands on
def partition_key_employee_events(employee_id: str) -> bytes:
    """Partition by employee_id for ordering guarantees per employee."""
    return employee_id.encode("utf-8")

def partition_key_risk_updates(employee_id: str) -> bytes:
    return employee_id.encode("utf-8")
