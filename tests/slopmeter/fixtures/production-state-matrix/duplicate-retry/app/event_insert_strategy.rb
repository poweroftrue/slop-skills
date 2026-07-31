class EventInsertStrategy
  def conflict_clause
    <<~SQL.strip
      ON CONFLICT (event_key) DO UPDATE
      SET line_id = EXCLUDED.line_id
    SQL
  end
end
