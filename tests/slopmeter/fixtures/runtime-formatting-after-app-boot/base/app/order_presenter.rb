class OrderPresenter
  def self.total(decimal_value)
    format("%.2f", decimal_value.coefficient * (10**decimal_value.exponent))
  end
end
