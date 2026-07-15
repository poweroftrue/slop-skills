require_relative "../lib/decimal_value"

module ApplicationDecimalFormatting
  def to_s
    format("%.2f", coefficient * (10**exponent))
  end
end

DecimalValue.prepend(ApplicationDecimalFormatting)
