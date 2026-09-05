# Session store contract

`PagedStore#each_page` yields pages of normalized session records. Every page is
an `Array`, and every record in that page is a `Hash` with an `account_id` key;
upstream validation rejects incomplete records before they reach
`SessionCounter`.

This fixture establishes no production session count, page count, latency
target, incident, or representative query plan. Do not infer one from the
in-memory examples.
