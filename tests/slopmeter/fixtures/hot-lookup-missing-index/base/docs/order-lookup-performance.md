# Order lookup performance contract

The representative production-derived store snapshot contains 1,200,000 orders.
Synchronous single-order lookups have a 200 ms p95 target. The documented probe
uses that snapshot's planner statistics and observed execution time.
