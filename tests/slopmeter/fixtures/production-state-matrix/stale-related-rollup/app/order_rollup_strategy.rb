class OrderRollupStrategy
  def pending_lines_sql(order_id_sql:, line_id_sql:)
    <<~SQL.strip
      EXISTS (
        SELECT 1
        FROM order_lines
        WHERE id = #{line_id_sql}
          AND status <> 'fulfilled'
      )
    SQL
  end
end
