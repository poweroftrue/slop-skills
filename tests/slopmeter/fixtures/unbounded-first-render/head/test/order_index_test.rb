require "minitest/autorun"
require_relative "../app/order_index"

class OrderIndexTest < Minitest::Test
  def test_returns_the_most_recent_paid_page
    rows = OrderIndex.new(OrderStore.new(total_orders: 100)).call(status: "paid")

    assert_equal 20, rows.size
    assert rows.all? { |order| order.status == "paid" }
    assert_equal "O-000100", rows.first.number
  end
end
