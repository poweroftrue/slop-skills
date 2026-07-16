require_relative "environment"

class OrderIndex
  PAGE_SIZE = 20

  def initialize(store)
    @store = store
  end

  def call(status:)
    @store.all
      .select { |order| order.status == status }
      .sort_by(&:created_at)
      .reverse
      .first(PAGE_SIZE)
  end
end
