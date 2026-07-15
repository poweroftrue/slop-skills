class RenderServiceRouter
  ROUTES = {
    ["POST", "/v2/render"] => :render,
    ["POST", "/v2/render/compat"] => :render_compatible
  }.freeze

  def resolve(method, path)
    ROUTES.fetch([method, path])
  end
end
