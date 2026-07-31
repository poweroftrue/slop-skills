class EventInsertStrategy
  def conflict_clause
    "ON CONFLICT (event_key) DO NOTHING"
  end
end
