# Runbook: Payment Webhook Failures and Idempotency Conflicts

## Overview
Operational triage for dropped payment webhooks and duplicate webhook delivery retries.

## Symptoms
- Webhook processor logging duplicate key errors or HTTP 500 responses.
- Discrepancy between third-party payment settlement and internal order completion.

## Root Causes
- Idempotency key cache eviction or distributed lock timeouts during high concurrency.
- Third-party webhook retry storm overwhelming consumer workers.

## Remediation Actions
1. **Clear Cache (`clear_cache`) - Low Risk**:
   - Evict corrupted or stuck idempotency validation locks in Redis. Auto-executable.
2. **Escalate Ticket (`create_escalation_ticket`) - Medium Risk**:
   - Dispatch to payment engineering if manual reconciliation is required.
