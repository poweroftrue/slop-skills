class OrderProcessor
  TERMINAL_STATUSES = %w[delivered fulfilled].freeze

  def initialize(notifier:)
    @notifier = notifier
  end

  def call(payload)
    return :ignored unless TERMINAL_STATUSES.include?(payload.fetch(:status))

    @notifier.delivered(payload.fetch(:order_id))
    :notified
  end
end
