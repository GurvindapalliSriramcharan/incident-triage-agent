# Runbook: Auth Redis Cache Latency and Connection Exhaustion

## Overview
Procedures for resolving Redis connection spikes and memory pressure affecting authentication token validations.

## Symptoms
- Logs indicating `Redis connection pool exhaustion` or connection latency > 200ms.
- Increased CPU utilization on the Redis cache tier.
- Intermittent token validation failures.

## Root Causes
- Expired session tokens not being evicted fast enough.
- Sudden spike in token verification traffic without connection reuse.
- Connection leaks from unclosed sessions.

## Remediation Actions
1. **Clear Cache (`clear_cache`) - Low Risk**:
   - Evict stale token cache entries and clear dead keys. Can be executed automatically.
2. **Restart Service (`restart_service`) - High Risk**:
   - If connection pool leaks persist inside auth service client instances, a rolling restart of the auth service is required to re-establish clean connection pools.
   - Requires Human Approval.
