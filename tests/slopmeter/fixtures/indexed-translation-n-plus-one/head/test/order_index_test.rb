require "minitest/autorun"
require_relative "../app/order_index"

class OrderIndexTest < Minitest::Test
  def test_lists_products_for_each_order
    names = {
      1 => { en: "Keyboard", ar: "لوحة مفاتيح" },
      2 => { en: "Mouse", ar: "فأرة" }
    }
    rows = OrderIndex.new(OrderRepository.new(names: names, query_log: QueryLog.new)).call

    assert_equal ["Keyboard"], rows.fetch(0).product_names
    assert_equal ["Mouse"], rows.fetch(1).product_names
  end
end
