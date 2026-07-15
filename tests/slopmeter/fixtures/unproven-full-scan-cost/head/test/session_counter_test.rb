require "minitest/autorun"
require_relative "../app/session_counter"

class PagedStore
  def initialize(pages)
    @pages = pages
  end

  def each_page
    @pages.each { |page| yield page }
  end
end

class SessionCounterTest < Minitest::Test
  def test_counts_sessions_for_an_account
    store = PagedStore.new([
      [{ account_id: "a" }, { account_id: "b" }],
      [{ account_id: "a" }]
    ])

    assert_equal 2, SessionCounter.new(store).count_for("a")
  end
end
