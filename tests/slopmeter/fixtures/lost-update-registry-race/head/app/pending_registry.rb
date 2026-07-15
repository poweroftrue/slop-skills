class PendingRegistry
  def initialize(store)
    @store = store
  end

  def add(account_id, operation_id)
    key = "pending:#{account_id}"
    current = @store.get(key) || []
    @store.set(key, current + [operation_id])
  end

  def take_all(account_id)
    key = "pending:#{account_id}"
    current = @store.get(key) || []
    @store.delete(key)
    current
  end
end
