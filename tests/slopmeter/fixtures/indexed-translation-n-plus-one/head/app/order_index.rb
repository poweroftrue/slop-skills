require_relative "environment"

class OrderIndex
  PAGE_SIZE = 20

  def initialize(repository)
    @repository = repository
  end

  def call
    @repository.page(limit: PAGE_SIZE, preload: [:order_lines, :products]).map do |order|
      names = order.order_lines.map { |line| line.variant.product.name }.uniq
      OrderIndexRow.new(number: order.number, product_names: names)
    end
  end
end
