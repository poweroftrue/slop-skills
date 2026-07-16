require_relative "environment"

class OrderIndex
  PAGE_SIZE = 20

  def initialize(store)
    @store = store
  end

  def call(status:)
    @store.page(status: status, limit: PAGE_SIZE)
  end
end
