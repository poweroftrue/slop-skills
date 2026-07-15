class KeyValueStore
  def initialize
    @values = {}
  end

  def get(key)
    @values[key]
  end

  def set(key, value)
    @values[key] = value
  end

  def delete(key)
    @values.delete(key)
  end
end
