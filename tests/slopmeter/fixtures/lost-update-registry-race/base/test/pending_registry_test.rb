require "minitest/autorun"
require_relative "../lib/key_value_store"
require_relative "../app/pending_registry"

class PendingRegistryTest < Minitest::Test
  def test_initializes
    assert PendingRegistry.new(KeyValueStore.new)
  end
end
