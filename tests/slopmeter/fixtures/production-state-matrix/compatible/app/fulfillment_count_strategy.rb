class FulfillmentCountStrategy
  COUNT_EXPRESSION = "LEAST(required_codes, fulfilled_codes + 1)".freeze

  def expression(observed:)
    COUNT_EXPRESSION
  end
end
