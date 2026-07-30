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

  def test_notifies_for_terminal_json_events
    notifier = FakeNotifier.new
    processor = OrderProcessor.new(notifier: notifier)

    assert_equal :notified, processor.call("order_id" => "order-1", "status" => "delivered")
    assert_equal :notified, processor.call("order_id" => "order-2", "status" => "fulfilled")
    assert_equal ["order-1", "order-2"], notifier.calls
  end
end
