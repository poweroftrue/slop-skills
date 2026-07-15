class TaskQueueClient
  def push(arguments)
    unless arguments.all? { |argument| scalar?(argument) }
      raise ArgumentError, "queue arguments must contain only scalar values"
    end

    true
  end

  private

  def scalar?(value)
    value.nil? || value.is_a?(String) || value.is_a?(Numeric) || value == true || value == false
  end
end
