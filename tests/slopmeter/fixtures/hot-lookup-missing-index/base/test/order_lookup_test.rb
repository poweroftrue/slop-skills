require "minitest/autorun"
require_relative "../app/order_lookup"

class OrderLookupTest < Minitest::Test
  def test_finds_an_order_by_number
    order = OrderLookup.new(OrderRepository.new).call(store_id: 9, number: "O-4")

    assert_equal "O-4", order.number
  end
end
