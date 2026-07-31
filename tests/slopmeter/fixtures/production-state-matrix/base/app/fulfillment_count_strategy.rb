class FulfillmentCountStrategy
  def expression(observed:)
    "LEAST(required_codes, fulfilled_codes + 1)"
  end
end
