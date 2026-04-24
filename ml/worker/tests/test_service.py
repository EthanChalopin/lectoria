import unittest

from ml.worker.service import WorkerService


class FakeSqsClient:
    def __init__(self):
        self.messages = []

    def send_message(self, QueueUrl, MessageBody):
        self.messages.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})


class FakeS3Client:
    def __init__(self):
        self.objects = []

    def put_object(self, **kwargs):
        self.objects.append(kwargs)


class FakeTable:
    def __init__(self):
        self.put_calls = []
        self.update_calls = []

    def put_item(self, **kwargs):
        self.put_calls.append(kwargs)

    def update_item(self, **kwargs):
        self.update_calls.append(kwargs)


class WorkerServiceTests(unittest.TestCase):
    def test_process_message_completed(self):
        sqs = FakeSqsClient()
        s3 = FakeS3Client()
        table = FakeTable()
        service = WorkerService(sqs_client=sqs, s3_client=s3, stories_table=table)

        msg = {
            "Body": '{"job_id":"job-1","story_id":"story-1","job_type":"sdxl","payload":{"prompt":"hello","style":"storybook"}}'
        }

        service.process_message(msg)

        self.assertEqual(len(s3.objects), 1)
        self.assertEqual(len(sqs.messages), 1)
        self.assertTrue(any(call["Key"]["story_id"] == "story-1" for call in table.update_calls))

    def test_process_message_unsupported_job_fails(self):
        sqs = FakeSqsClient()
        s3 = FakeS3Client()
        table = FakeTable()
        service = WorkerService(sqs_client=sqs, s3_client=s3, stories_table=table)

        msg = {
            "Body": '{"job_id":"job-1","story_id":"story-1","job_type":"unknown","payload":{}}'
        }

        with self.assertRaises(ValueError):
            service.process_message(msg)

        self.assertEqual(len(sqs.messages), 1)
        self.assertTrue(any(call["Key"]["story_id"] == "story-1" for call in table.update_calls))


if __name__ == "__main__":
    unittest.main()
