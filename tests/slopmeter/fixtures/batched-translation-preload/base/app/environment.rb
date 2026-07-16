class QueryLog
  Entry = Struct.new(:table, :index, :rows, keyword_init: true)

  attr_reader :entries

  def initialize
    @entries = []
  end

  def record(table:, index:, rows:)
    entries << Entry.new(table: table, index: index, rows: rows)
  end

  def count(table)
    entries.count { |entry| entry.table == table }
  end

  def all_indexed?
    entries.all? { |entry| entry.index }
  end
end

class TranslationStore
  def initialize(names, query_log)
    @names = names
    @query_log = query_log
  end

  def fetch_for_product(product_id)
    @query_log.record(
      table: "product_translations",
      index: "index_product_translations_on_product_locale",
      rows: 2
    )
    @names.fetch(product_id)
  end

  def fetch_for_products(product_ids)
    @query_log.record(
      table: "product_translations",
      index: "index_product_translations_on_product_locale",
      rows: product_ids.size * 2
    )
    product_ids.to_h { |product_id| [product_id, @names.fetch(product_id)] }
  end
end

class Product
  attr_reader :id

  def initialize(id:, translation_store:, preloaded_names: nil)
    @id = id
    @translation_store = translation_store
    @preloaded_names = preloaded_names
  end

  def name(locale = :en)
    names = @preloaded_names || @translation_store.fetch_for_product(id)
    names.fetch(locale)
  end
end

Variant = Struct.new(:product, keyword_init: true)
OrderLine = Struct.new(:variant, keyword_init: true)
Order = Struct.new(:number, :order_lines, keyword_init: true)
OrderIndexRow = Struct.new(:number, :product_names, keyword_init: true)

class OrderRepository
  def initialize(names:, query_log:)
    @names = names
    @query_log = query_log
    @translation_store = TranslationStore.new(names, query_log)
  end

  def page(limit:, preload:)
    product_ids = @names.keys.sort.first(limit)
    @query_log.record(table: "orders", index: "idx_orders_on_store_created_at", rows: product_ids.size)
    @query_log.record(table: "order_lines", index: "index_order_lines_on_order_id", rows: product_ids.size) if preload.include?(:order_lines)
    @query_log.record(table: "products", index: "PRIMARY", rows: product_ids.size) if preload.include?(:products)

    names_by_product = if preload.include?(:translations)
      @translation_store.fetch_for_products(product_ids)
    else
      {}
    end

    product_ids.map do |product_id|
      product = Product.new(
        id: product_id,
        translation_store: @translation_store,
        preloaded_names: names_by_product[product_id]
      )
      line = OrderLine.new(variant: Variant.new(product: product))
      Order.new(number: format("O-%03d", product_id), order_lines: [line])
    end
  end
end
