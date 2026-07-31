require_relative "fulfillment_count_strategy"
require_relative "delivery_timing"
require_relative "event_insert_strategy"
require_relative "order_rollup_strategy"

class FulfillmentService
  attr_reader :count_strategy, :delivery_timing, :event_insert_strategy,
    :last_ruby_state, :order_rollup_strategy

  def initialize(
    database:,
    delivery_gateway:,
    count_strategy: FulfillmentCountStrategy.new,
    delivery_timing: DeliveryTiming.new,
    event_insert_strategy: EventInsertStrategy.new,
    order_rollup_strategy: OrderRollupStrategy.new
  )
    @database = database
    @delivery_gateway = delivery_gateway
    @count_strategy = count_strategy
    @delivery_timing = delivery_timing
    @event_insert_strategy = event_insert_strategy
    @order_rollup_strategy = order_rollup_strategy
    @last_ruby_state = nil
  end

  def call(line_id:, event_key:, before_write: nil, fail_before_commit: false)
    input = {
      "line_id" => line_id,
      "event_key" => event_key,
      "fail_before_commit" => fail_before_commit
    }
    observed = @database.query_row(<<~SQL)
      SELECT json_build_object(
        'line_id', current_line.id,
        'order_id', current_line.order_id,
        'required_codes', current_line.required_codes,
        'fulfilled_codes', current_line.fulfilled_codes,
        'status', current_line.status,
        'pending_sibling_count', (
          SELECT count(*)
          FROM order_lines AS sibling
          WHERE sibling.order_id = current_line.order_id
            AND sibling.id <> current_line.id
            AND sibling.status <> 'fulfilled'
        )
      )::text
      FROM order_lines AS current_line
      WHERE current_line.id = #{@database.quote(line_id)};
    SQL
    raise KeyError, "unknown line" unless observed

    @last_ruby_state = {
      "input_class" => input.class.name,
      "input" => input,
      "cached_line_before" => observed,
      "result" => nil,
      "exception" => nil
    }

    before_write&.call
    pre_notified = delivery_timing.before_transaction(
      observed: observed,
      event_key: event_key,
      gateway: @delivery_gateway
    )
    @last_ruby_state = @last_ruby_state.merge(
      "outbound_before_commit" => pre_notified
    )
    result = @database.query_row(transaction_sql(
      observed: observed,
      event_key: event_key,
      fail_before_commit: fail_before_commit
    ))

    @last_ruby_state = @last_ruby_state.merge(
      "cached_line_after" => observed,
      "result" => result
    )
    delivery_timing.after_commit(
      result: result,
      pre_notified: pre_notified,
      gateway: @delivery_gateway
    )
    result
  rescue StandardError => exception
    @last_ruby_state = (@last_ruby_state || {
      "input_class" => input.class.name,
      "input" => input
    }).merge(
      "result" => nil,
      "exception" => "#{exception.class}: #{exception.message.lines.first.to_s.strip}"
    )
    raise
  end

  private

  def transaction_sql(observed:, event_key:, fail_before_commit:)
    line_id = @database.quote(observed.fetch("line_id"))
    order_id = @database.quote(observed.fetch("order_id"))
    event_key = @database.quote(event_key)
    next_count = count_strategy.expression(observed: observed)
    conflict_clause = event_insert_strategy.conflict_clause
    pending_lines = order_rollup_strategy.pending_lines_sql(
      order_id_sql: order_id,
      line_id_sql: line_id
    )
    forced_failure = if fail_before_commit
      "DO $rollback$ BEGIN RAISE EXCEPTION 'synthetic rollback'; END $rollback$;"
    end

    <<~SQL
      BEGIN ISOLATION LEVEL READ COMMITTED;
      CREATE TEMP TABLE event_state (
        inserted boolean NOT NULL DEFAULT false,
        old_order_status text
      ) ON COMMIT DROP;
      INSERT INTO event_state DEFAULT VALUES;

      WITH inserted_event AS (
        INSERT INTO fulfillment_events(event_key, line_id)
        VALUES (#{event_key}, #{line_id})
        #{conflict_clause}
        RETURNING event_key
      )
      UPDATE event_state
      SET inserted = EXISTS (SELECT 1 FROM inserted_event);

      UPDATE order_lines
      SET fulfilled_codes = #{next_count},
          status = CASE
            WHEN #{next_count} >= required_codes THEN 'fulfilled'
            ELSE 'processing'
          END
      WHERE id = #{line_id}
        AND (SELECT inserted FROM event_state);

      WITH locked_order AS (
        SELECT status
        FROM orders
        WHERE id = #{order_id}
        FOR UPDATE
      )
      UPDATE event_state
      SET old_order_status = (SELECT status FROM locked_order);

      UPDATE orders
      SET status = CASE
        WHEN #{pending_lines} THEN 'processing'
        ELSE 'fulfilled'
      END
      WHERE id = #{order_id};

      #{forced_failure}

      SELECT json_build_object(
        'inserted', (SELECT inserted FROM event_state),
        'transitioned', (
          (SELECT inserted FROM event_state)
          AND (SELECT old_order_status FROM event_state) <> 'fulfilled'
          AND (SELECT status FROM orders WHERE id = #{order_id}) = 'fulfilled'
        ),
        'order_id', #{order_id},
        'line', (
          SELECT row_to_json(line_state)
          FROM (
            SELECT id, order_id, required_codes, fulfilled_codes, status
            FROM order_lines
            WHERE id = #{line_id}
          ) AS line_state
        ),
        'order_status', (SELECT status FROM orders WHERE id = #{order_id}),
        'backend_pid', pg_backend_pid(),
        'isolation', current_setting('transaction_isolation')
      )::text
      FROM event_state;
      COMMIT;
    SQL
  end
end
