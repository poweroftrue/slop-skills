require "minitest/autorun"
require_relative "../app/order_processor"

class OrderProcessorTest < Minitest::Test
  class FakeNotifier
    attr_reader :calls

    def initialize
      @calls = []
    end

    def delivered(order_id)
      calls << order_id
    end
  end

  def test_notifies_for_delivered_json_event
    notifier = FakeNotifier.new
    result = OrderProcessor.new(notifier: notifier).call(
      "order_id" => "order-1",
      "status" => "delivered"
    )

    assert_equal :notified, result
    assert_equal ["order-1"], notifier.calls
  end
end
