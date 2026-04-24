import unittest

from ml.worker.message_schema import JobMessage


class JobMessageTests(unittest.TestCase):
    def test_valid_message(self):
        msg = {
            "Body": '{"job_id":"job-1","story_id":"story-1","job_type":"sdxl","payload":{"prompt":"hi"}}'
        }
        job = JobMessage.from_sqs_message(msg)
        self.assertEqual(job.job_id, "job-1")
        self.assertEqual(job.story_id, "story-1")
        self.assertEqual(job.job_type, "sdxl")
        self.assertEqual(job.payload["prompt"], "hi")

    def test_story_id_defaults_to_job_id(self):
        msg = {"Body": '{"job_id":"job-1","job_type":"sdxl","payload":{}}'}
        job = JobMessage.from_sqs_message(msg)
        self.assertEqual(job.story_id, "job-1")

    def test_invalid_message_raises(self):
        with self.assertRaises(ValueError):
            JobMessage.from_sqs_message({"Body": '{"job_type":"sdxl"}'})


if __name__ == "__main__":
    unittest.main()
