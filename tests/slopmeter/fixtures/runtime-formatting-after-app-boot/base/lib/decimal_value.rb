class DecimalValue
  attr_reader :coefficient, :exponent

  def initialize(coefficient, exponent)
    @coefficient = coefficient
    @exponent = exponent
  end

  def to_s
    "#{coefficient}e#{exponent}"
  end
end
