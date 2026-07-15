require "minitest/autorun"
require_relative "../lib/key_value_store"
require_relative "../app/pending_registry"

class PendingRegistryTest < Minitest::Test
  def test_adds_and_takes_pending_operations
    registry = PendingRegistry.new(KeyValueStore.new)

    registry.add("account-4", "operation-a")
    registry.add("account-4", "operation-b")

    assert_equal ["operation-a", "operation-b"], registry.take_all("account-4")
    assert_empty registry.take_all("account-4")
  end
end
