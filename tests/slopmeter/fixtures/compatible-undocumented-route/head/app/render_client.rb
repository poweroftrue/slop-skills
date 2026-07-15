class RenderClient
  def initialize(transport)
    @transport = transport
  end

  def submit(payload)
    path = payload.fetch(:compatibility_mode, false) ? "/v2/render/compat" : "/v2/render"
    @transport.post(path, payload)
  end
end
