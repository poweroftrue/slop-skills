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
    submission = Submission.new("submission-7")

    SubmissionService.new(queue).schedule(submission)

    assert_equal [submission], queue.arguments
  end
end
