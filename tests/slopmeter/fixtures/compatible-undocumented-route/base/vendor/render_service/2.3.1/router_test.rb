require "minitest/autorun"
require_relative "router"

class RenderServiceRouterTest < Minitest::Test
  def test_compatibility_route
    assert_equal :render_compatible,
                 RenderServiceRouter.new.resolve("POST", "/v2/render/compat")
  end
end
