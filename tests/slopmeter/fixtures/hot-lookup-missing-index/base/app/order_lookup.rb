require_relative "environment"

class OrderLookup
  def initialize(repository)
    @repository = repository
  end

  def call(store_id:, number:)
    @repository.find_by_number(store_id: store_id, number: number)
  end
end
