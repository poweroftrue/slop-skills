class RenderClient
  def initialize(transport)
    @transport = transport
  end

  def submit(payload)
    @transport.post("/v2/render", payload)
  end
end
