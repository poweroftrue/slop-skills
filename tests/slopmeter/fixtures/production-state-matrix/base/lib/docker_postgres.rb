require "json"
require "open3"

class DockerPostgres
  class QueryError < StandardError; end

  def initialize(container_name)
    @container_name = container_name
  end

  def exec(sql)
    stdout, stderr, status = Open3.capture3(
      "docker", "exec", "-i", @container_name,
      "psql", "-X", "-q", "-v", "ON_ERROR_STOP=1",
      "-U", "postgres", "-d", "postgres", "-A", "-t",
      stdin_data: sql
    )
    return stdout if status.success?

    detail = stderr.lines.find { |line| !line.strip.empty? }.to_s.strip
    raise QueryError, detail.empty? ? "local PostgreSQL query failed" : detail
  end

  def query_row(sql)
    line = exec(sql).lines.map(&:strip).reject(&:empty?).last
    line && JSON.parse(line)
  end

  def quote(value)
    "'#{value.to_s.gsub("'", "''")}'"
  end
end
