# Runbook: Authentication Service Timeouts and 504 Gateway Errors

## Overview
This runbook covers operational troubleshooting and remediation for HTTP 504 Gateway Timeouts and token refresh timeouts on the `auth` service.

## Symptoms
- Clients receiving 504 Gateway Timeout during `/oauth/token` or login workflows.
- Increased p99 latency on authentication endpoints (> 1000ms).
- High rate of token refresh lock wait timeouts in auth service logs.
- Degraded replica health reported by service mesh.

## Root Causes
1. **Redis Cache Latency & Pool Saturation**: Heavy load or network latency on Redis token store causing threads to block on token blacklist lookups.
2. **Token Refresh Lock Contention**: Concurrent token refresh requests for the same client credentials causing distributed lock contention.
3. **Overloaded Auth Replicas**: High memory usage or stuck worker threads across auth service pods requiring a graceful restart.

## Investigation Steps
1. Inspect health endpoints of the `auth` service.
2. Examine recent logs for `token refresh timeout`, `read lock wait timeout`, and Redis connection latency.
3. Check Redis memory and connection pool utilization.

## Remediation Actions
1. **Clear Cache (Low Risk)**:
   - If Redis connection latency is caused by expired token keys, run `clear_cache` for the `auth` service.
2. **Restart Service Replicas (High Risk - Requires Human Approval)**:
   - If auth replicas are degraded, memory saturated, or worker threads are stuck in lock contention, execute `restart_service` on `auth`.
   - **Policy**: This is a HIGH risk action and strictly requires human approval from the on-call engineer.
3. **Escalate Ticket (Medium Risk)**:
   - If restarting replicas does not resolve latency or error rates persist, create an escalation ticket to security engineering.
