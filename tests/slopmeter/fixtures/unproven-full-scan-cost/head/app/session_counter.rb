class SessionCounter
  def initialize(store)
    @store = store
  end

  def count_for(account_id)
    count = 0
    @store.each_page do |sessions|
      count += sessions.count { |session| session.fetch(:account_id) == account_id }
    end
    count
  end
end
