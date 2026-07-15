require "minitest/autorun"
require_relative "../app/submission"
require_relative "../app/submission_service"

class RecordingQueue
  attr_reader :arguments

  def push(arguments)
    @arguments = arguments
  end
end

class SubmissionServiceTest < Minitest::Test
  def test_schedules_submission
    queue = RecordingQueue.new

    SubmissionService.new(queue).schedule(Submission.new("submission-7"))

    assert_equal ["submission-7"], queue.arguments
  end
end
