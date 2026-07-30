class OrderProcessor
  def initialize(notifier:)
    @notifier = notifier
  end

  def call(payload)
    return :ignored unless payload.fetch("status") == "delivered"

    @notifier.delivered(payload.fetch("order_id"))
    :notified
  end
end
