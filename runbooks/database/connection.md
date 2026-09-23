# Runbook: Database Connection Pool Starvation

## Overview
Remediation procedures when services cannot acquire database connections from PgBouncer or connection pools.

## Symptoms
- Logs report `remaining connection slots are reserved for non-replication superuser connections` or `connection pool exhausted`.
- Client application request queues backing up.

## Root Causes
- Leaked connections from unclosed application sessions.
- Traffic burst without dynamic connection pool throttling.
- Long-running queries keeping connection slots occupied.

## Remediation Actions
1. **Terminate Idle Transactions (`terminate_idle_transaction`) - High Risk**:
   - Terminate connection sessions holding inactive connections.
   - Requires Human Approval.
2. **Escalate Ticket (`create_escalation_ticket`) - Medium Risk**:
   - Notify database administrators if pool resize is needed.
