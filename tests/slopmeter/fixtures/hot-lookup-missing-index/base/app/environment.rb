Order = Struct.new(:store_id, :number, :gateway_reference, keyword_init: true)
QueryPlan = Struct.new(:access, :key, :rows_examined, :actual_ms, keyword_init: true)

class OrderRepository
  TABLE_ROWS = 1_200_000

  attr_reader :last_plan

  def find_by_number(store_id:, number:)
    @last_plan = QueryPlan.new(
      access: "const",
      key: "idx_orders_on_store_and_number",
      rows_examined: 1,
      actual_ms: 1.2
    )
    Order.new(store_id: store_id, number: number, gateway_reference: "gw-#{number}")
  end

  def find_by_gateway_reference(store_id:, gateway_reference:)
    @last_plan = QueryPlan.new(
      access: "ALL",
      key: nil,
      rows_examined: TABLE_ROWS,
      actual_ms: 780.0
    )
    Order.new(store_id: store_id, number: "O-900", gateway_reference: gateway_reference)
  end
end
