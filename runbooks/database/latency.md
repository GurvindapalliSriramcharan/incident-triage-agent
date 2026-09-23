# Runbook: Database Query Latency and Connection Saturation

## Overview
Operational guide for handling elevated database query latency, CPU spikes, and connection saturation on primary PostgreSQL clusters.

## Symptoms
- Query execution latency p95 > 2500ms.
- Application services reporting database connection timeouts.
- High number of `idle in transaction` queries holding table locks.
- Database CPU utilization exceeding 90%.

## Root Causes
1. **Long-running Idle Transactions**: Unclosed transactions blocking vacuum operations and holding row-level locks.
2. **Lock Contention**: Conflicting DDL or unindexed foreign key updates blocking concurrent writes.
3. **Primary Node Saturation**: Exhaustion of CPU/IOPS on the primary database instance.

## Remediation Actions
1. **Terminate Idle Transactions (`terminate_idle_transaction`) - High Risk**:
   - Safely terminate sessions in state `idle in transaction` older than 300 seconds.
   - **Policy**: High risk action. Requires on-call operator approval to ensure active background tasks are not abruptly severed without verification.
2. **Database Failover (`failover_database`) - Critical Risk**:
   - If the primary database hardware or CPU is completely unresponsive, initiate failover to standby replica.
   - **Policy**: CRITICAL risk. Requires explicit approval and strict verification.
