require "minitest/autorun"
require_relative "../config/environment"
require_relative "../app/order_presenter"

class OrderPresenterTest < Minitest::Test
  def test_total_uses_application_decimal_formatting
    assert_equal "1.25", OrderPresenter.total(DecimalValue.new(125, -2))
  end
end
