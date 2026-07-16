require_relative "environment"

class OrderIndex
  PAGE_SIZE = 20

  def initialize(repository)
    @repository = repository
  end

  def call
    @repository.page(limit: PAGE_SIZE, preload: [:order_lines]).map do |order|
      OrderIndexRow.new(number: order.number)
    end
  end
end
