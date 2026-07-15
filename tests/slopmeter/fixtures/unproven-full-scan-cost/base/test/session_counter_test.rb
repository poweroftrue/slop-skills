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
  def test_initializes
    assert SessionCounter.new(PagedStore.new([]))
  end
end
