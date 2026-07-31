# Fulfillment event contract

The order is fulfilled only when every active line has received its required
number of successful code events.

- An event key is idempotent: retrying or redelivering it must not increment a
  line twice.
- A failed transaction leaves the event, line, and order unchanged.
- A rolled-back event may be retried successfully.
- Concurrent distinct events for the same line are supported.
- The delivery gateway is called once on the committed transition from
  `processing` to `fulfilled`, never before commit and never for a rollback.

Production has orders with multiple lines and lines requiring more than one
code. The local matrix must preserve those cardinalities while replacing all
identifiers and generating failure and interleaving cases only in local state.
