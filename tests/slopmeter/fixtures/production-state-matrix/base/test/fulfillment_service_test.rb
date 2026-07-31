require "minitest/autorun"
require_relative "../app/fulfillment_service"

class FulfillmentServiceTest < Minitest::Test
  class FakeDatabase
    attr_reader :transaction_sql

    def quote(value)
      "'#{value}'"
    end

    def query_row(sql)
      if sql.include?("BEGIN ISOLATION LEVEL")
        @transaction_sql = sql
        {
          "inserted" => true,
          "transitioned" => true,
          "order_id" => "order-1",
          "order_status" => "fulfilled"
        }
      else
        {
          "line_id" => "line-1",
          "order_id" => "order-1",
          "required_codes" => 1,
          "fulfilled_codes" => 0,
          "status" => "processing",
          "pending_sibling_count" => 0
        }
      end
    end
  end

  class FakeGateway
    attr_reader :calls

    def initialize
      @calls = []
    end

    def delivered(order_id)
      calls << order_id
    end
  end

  def test_processes_one_successful_event
    database = FakeDatabase.new
    gateway = FakeGateway.new
    result = FulfillmentService.new(
      database: database,
      delivery_gateway: gateway
    ).call(line_id: "line-1", event_key: "event-1")

    assert_equal "fulfilled", result.fetch("order_status")
    assert_equal ["order-1"], gateway.calls
    assert_includes database.transaction_sql, "ON CONFLICT (event_key)"
  end
end
