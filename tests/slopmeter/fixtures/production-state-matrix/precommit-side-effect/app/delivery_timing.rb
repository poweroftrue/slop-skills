class DeliveryTiming
  def initialize
    @seen_event_keys = {}
  end

  def before_transaction(observed:, event_key:, gateway:)
    return false if @seen_event_keys[event_key]

    @seen_event_keys[event_key] = true
    will_fulfill = Integer(observed.fetch("fulfilled_codes")) + 1 >=
      Integer(observed.fetch("required_codes"))
    return false unless will_fulfill &&
      Integer(observed.fetch("pending_sibling_count")).zero?

    gateway.delivered(observed.fetch("order_id"))
    true
  end

  def after_commit(result:, pre_notified:, gateway:)
    return unless result.fetch("transitioned")
    return if pre_notified

    gateway.delivered(result.fetch("order_id"))
  end
end
