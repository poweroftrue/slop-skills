require "minitest/autorun"
require_relative "../app/order_lookup"

class OrderLookupTest < Minitest::Test
  def test_finds_an_order_by_gateway_reference
    order = OrderLookup.new(OrderRepository.new).call(
      store_id: 9,
      gateway_reference: "provider-7788"
    )

    assert_equal "provider-7788", order.gateway_reference
  end
end
