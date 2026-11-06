# Benchmark Run Artifacts — RUN-20261106-155200

- **Timestamp:** `2026-11-06T15:52:00.504814+00:00`
- **Total Scenarios:** 16
- **Hindsight Status:** `OFFLINE_PREVIEW` (Bank: `opsrecall-demo`)
- **Model Configured:** `openai/gpt-oss-120b`
- **Composite Score:** **Memory ON: 97.9** vs. **Memory OFF: 84.6** (Delta: `+13.3` pts)

## Artifacts in this Directory
- `summary.json`: Macro evaluation summary and 16-dimensional metrics
- `case_results.json`: Isolated evaluation results for each of the 16 scenarios
- `metric_details.json`: Side-by-side comparison across all 16 metrics
- `calibration_details.json`: Brier score, ECE, and reliability bin partitions
- `run_metadata.json`: Run identity, configuration, and environment provenance

## Per-Scenario Summary
| Case ID | Service | Scenario Type | Mem OFF | Mem ON | Delta | Avoided Failed Fix |
|:---|:---|:---|:---:|:---:|:---:|:---:|
| `EVAL-001` | `checkout-api` | `recurrent_incident` | 57.0 | 99.5 | `+42.5` | Yes |
| `EVAL-002` | `order-fulfillment-worker` | `recurrent_incident` | 57.0 | 100.0 | `+43.0` | Yes |
| `EVAL-003` | `payment-gateway` | `recurrent_incident` | 57.0 | 99.5 | `+42.5` | Yes |
| `EVAL-004` | `catalog-service` | `recurrent_incident` | 67.0 | 99.5 | `+32.5` | Yes |
| `EVAL-005` | `checkout-orchestrator` | `recurrent_incident` | 47.0 | 99.5 | `+52.5` | Yes |
| `EVAL-006` | `cdn-edge` | `novel_distractor` | 99.5 | 99.5 | `+0.0` | Yes |
| `EVAL-007` | `checkout-api` | `different_underlying_cause` | 100.0 | 100.0 | `+0.0` | Yes |
| `EVAL-008` | `auth-api` | `unrelated_service_failure` | 95.0 | 95.0 | `+0.0` | Yes |
| `EVAL-009` | `inventory-worker` | `missing_deployment_info` | 95.0 | 95.0 | `+0.0` | Yes |
| `EVAL-010` | `order-fulfillment-worker` | `conflicting_evidence` | 100.0 | 100.0 | `+0.0` | Yes |
| `EVAL-011` | `catalog-service` | `unsafe_historical_fix` | 90.0 | 90.0 | `+0.0` | Yes |
| `EVAL-012` | `event-streaming-pipeline` | `novel_incident` | 94.5 | 94.5 | `+0.0` | Yes |
| `EVAL-013` | `payment-gateway` | `deployment_regression` | 95.0 | 95.0 | `+0.0` | Yes |
| `EVAL-014` | `checkout-orchestrator` | `cascading_service_failure` | 100.0 | 100.0 | `+0.0` | Yes |
| `EVAL-015` | `catalog-service` | `contradictory_historical_memory` | 100.0 | 100.0 | `+0.0` | Yes |
| `EVAL-016` | `checkout-api` | `insufficient_evidence_ambiguity` | 100.0 | 100.0 | `+0.0` | Yes |
