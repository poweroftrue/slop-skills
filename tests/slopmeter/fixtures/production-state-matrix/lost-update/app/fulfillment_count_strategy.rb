class FulfillmentCountStrategy
  def expression(observed:)
    next_count = Integer(observed.fetch("fulfilled_codes")) + 1
    "LEAST(required_codes, #{next_count})"
  end
end
