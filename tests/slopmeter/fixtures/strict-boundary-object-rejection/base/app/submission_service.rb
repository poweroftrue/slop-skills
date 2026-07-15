class SubmissionService
  def initialize(queue)
    @queue = queue
  end

  def schedule(submission)
    @queue.push([submission.id])
  end
end
