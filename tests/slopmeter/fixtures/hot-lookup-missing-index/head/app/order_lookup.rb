require_relative "environment"

class OrderLookup
  def initialize(repository)
    @repository = repository
  end

  def call(store_id:, number: nil, gateway_reference: nil)
    if gateway_reference
      @repository.find_by_gateway_reference(
        store_id: store_id,
        gateway_reference: gateway_reference
      )
    else
      @repository.find_by_number(store_id: store_id, number: number)
    end
  end
end
