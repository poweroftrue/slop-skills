require "minitest/autorun"
require_relative "../app/order_index"

class OrderIndexTest < Minitest::Test
  def test_lists_orders
    names = {
      1 => { en: "Keyboard", ar: "لوحة مفاتيح" },
      2 => { en: "Mouse", ar: "فأرة" }
    }
    rows = OrderIndex.new(OrderRepository.new(names: names, query_log: QueryLog.new)).call

    assert_equal ["O-001", "O-002"], rows.map(&:number)
  end
end
