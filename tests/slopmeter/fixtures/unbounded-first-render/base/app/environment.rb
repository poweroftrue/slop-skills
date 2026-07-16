Order = Struct.new(:number, :status, :created_at, keyword_init: true)

class OrderStore
  attr_reader :rows_examined, :objects_materialized, :index_used

  def initialize(total_orders:)
    @total_orders = total_orders
    @rows_examined = 0
    @objects_materialized = 0
    @index_used = nil
  end

  def page(status:, limit:)
    matching_ids = (1..@total_orders).lazy.select { |id| status_for(id) == status }.first(limit)
    @rows_examined = matching_ids.size
    @objects_materialized = matching_ids.size
    @index_used = "idx_orders_on_store_status_created_at"
    matching_ids.map { |id| build_order(id) }
  end

  def all
    @rows_examined = @total_orders
    @objects_materialized = @total_orders
    @index_used = nil
    (1..@total_orders).map { |id| build_order(id) }
  end

  private

  def build_order(id)
    Order.new(number: format("O-%06d", id), status: status_for(id), created_at: id)
  end

  def status_for(id)
    id.even? ? "paid" : "pending"
  end
end
