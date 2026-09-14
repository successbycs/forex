# H_SLOW stream-isolation declaration v1

Status: **local, disabled planning kernel**. This document describes a pure
registry validation format. It neither provisions an account nor selects a
saved terminal/login, writes state, obtains a lease, or enables an order path.

`forex.stream_isolation.validate_stream_registry` accepts exactly two entries:
the retained M1 owner and H_SLOW. Each entry declares an opaque Demo account
scope, opaque terminal-instance label, and unique logical namespaces for state,
monitoring, leases, reservations and outcomes. These labels deliberately are
not account numbers, terminal paths, credentials or storage locations.

```python
{
  "schema_version": "forex.stream-isolation.v1",
  "streams": [
    {
      "stream_id": "M1",
      "server": "GOMarketsMU-Demo",
      "account_scope": "demo_scope_m1",
      "terminal_instance": "terminal_instance_m1",
      "namespaces": {
        "state_namespace": "state_m1",
        "monitor_namespace": "monitor_m1",
        "lease_namespace": "lease_m1",
        "reservation_namespace": "reservation_m1",
        "outcome_namespace": "outcome_m1"
      },
      "deployment_state": "RETAINED_EXISTING_OPERATION",
      "account_selection": "NOT_SELECTED",
      "execution_capability": "NOT_EXPOSED"
    },
    {
      "stream_id": "H_SLOW",
      "server": "GOMarketsMU-Demo",
      "account_scope": "demo_scope_hslow",
      "terminal_instance": "terminal_instance_hslow",
      "namespaces": {
        "state_namespace": "state_hslow",
        "monitor_namespace": "monitor_hslow",
        "lease_namespace": "lease_hslow",
        "reservation_namespace": "reservation_hslow",
        "outcome_namespace": "outcome_hslow"
      },
      "deployment_state": "NOT_DEPLOYED",
      "account_selection": "NOT_SELECTED",
      "execution_capability": "NOT_EXPOSED"
    }
  ]
}
```

The closed schema rejects duplicate account/terminal/namespace labels, any
server other than `GOMarketsMU-Demo`, unknown streams, an active H_SLOW state,
or extra fields that might smuggle in login, routing or execution authority.
It returns a deterministic hash of the full declaration and a redacted status
projection. Rechecking against a recorded hash detects later plan drift.

Passing this validation is engineering evidence only. Before any activation,
the operator must separately authorise exact Demo account and terminal routing,
aggregate and per-stream limits, protections, holding and cost treatment, and
the production execution/reconciliation integration. `GOMarketsMU-Live`
remains forbidden.
