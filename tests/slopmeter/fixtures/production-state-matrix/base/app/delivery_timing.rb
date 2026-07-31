class DeliveryTiming
  def before_transaction(observed:, event_key:, gateway:)
    false
  end

  def after_commit(result:, pre_notified:, gateway:)
    return unless result.fetch("transitioned")
    return if pre_notified

    gateway.delivered(result.fetch("order_id"))
  end
end
