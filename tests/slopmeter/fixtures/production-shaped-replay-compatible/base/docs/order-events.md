# Order event contract

The application receives JSON-decoded order events with string keys. Production
currently emits both `delivered` and `fulfilled` as terminal statuses. A
terminal event must enqueue one delivery notification.
