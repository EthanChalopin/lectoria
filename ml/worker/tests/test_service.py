import unittest
from unittest.mock import patch
import json

from ml.worker.service import WorkerService


class FakeSqsClient:
    def __init__(self):
        self.messages = []

    def send_message(self, QueueUrl, MessageBody):
        self.messages.append({"QueueUrl": QueueUrl, "MessageBody": MessageBody})


class FakeS3Client:
    def __init__(self):
        self.objects = []
        self.object_map = {}

    def put_object(self, **kwargs):
        self.objects.append(kwargs)
        self.object_map[kwargs["Key"]] = kwargs["Body"]

    def get_object(self, Bucket, Key):
        del Bucket

        class BodyWrapper:
            def __init__(self, payload):
                self.payload = payload

            def read(self):
                return self.payload

        return {"Body": BodyWrapper(self.object_map[Key])}


class FakeTable:
    def __init__(self):
        self.put_calls = []
        self.update_calls = []

    def put_item(self, **kwargs):
        self.put_calls.append(kwargs)

    def update_item(self, **kwargs):
        self.update_calls.append(kwargs)


class WorkerServiceTests(unittest.TestCase):
    @patch("ml.worker.handlers.render_png_bytes", return_value=b"fake-png")
    def test_process_message_completed(self, _mock_render_png_bytes):
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

    @patch(
        "ml.worker.handlers.build_story_plan",
        return_value={
            "title": "Forest Lights",
            "logline": "A gentle discovery.",
            "world_description": "A warm magical forest.",
            "visual_style_prompt": "storybook",
            "chapters": [
                {
                    "chapter_number": 1,
                    "title": "The First Clue",
                    "summary": "Lina finds a glowing path.",
                    "goal": "Begin the story.",
                    "visual_focus": "fireflies in a moonlit clearing",
                }
            ],
        },
    )
    def test_story_plan_enqueues_first_chapter(self, _mock_build_story_plan):
        sqs = FakeSqsClient()
        s3 = FakeS3Client()
        table = FakeTable()
        service = WorkerService(sqs_client=sqs, s3_client=s3, stories_table=table)

        msg = {
            "Body": (
                '{"job_id":"story-1","story_id":"story-1","job_type":"story_plan",'
                '"payload":{"book_prompt":"A magical walk","child_name":"Lina","chapter_count":1}}'
            )
        }

        service.process_message(msg)

        self.assertEqual(len(s3.objects), 3)
        self.assertEqual(len(sqs.messages), 1)
        self.assertIn('"job_type": "chapter_generate"', sqs.messages[0]["MessageBody"])
        self.assertTrue(any(call["Key"]["story_id"] == "story-1" for call in table.update_calls))

    @patch(
        "ml.worker.handlers.build_chapter",
        return_value={
            "chapter_number": 1,
            "title": "The First Clue",
            "summary": "Lina finds a glowing path.",
            "chapter_text": "Short text.",
            "visual_prompt": "A child in a glowing forest clearing, storybook illustration",
            "negative_prompt": "blurry",
            "continuity_state": {"location": "forest"},
            "image_alt": "Lina in the forest",
        },
    )
    def test_chapter_generate_enqueues_next_text_step_not_image(self, _mock_build_chapter):
        sqs = FakeSqsClient()
        s3 = FakeS3Client()
        table = FakeTable()
        service = WorkerService(sqs_client=sqs, s3_client=s3, stories_table=table)

        manifest = {
            "story_id": "story-1",
            "status": "in_progress",
            "phase": "text",
            "brief": {"art_direction": {"style": "storybook"}},
            "chapters_total": 2,
            "chapters_completed": 0,
            "chapters_text_completed": 0,
            "chapters_images_completed": 0,
            "chapters": [
                {"chapter_number": 1, "status": "queued"},
                {"chapter_number": 2, "status": "queued"},
            ],
        }
        plan = {
            "chapters": [
                {"chapter_number": 1, "title": "The First Clue", "summary": "Lina finds a glowing path."},
                {"chapter_number": 2, "title": "The Lake", "summary": "Lina reaches the lake."},
            ]
        }
        s3.object_map["stories/story-1/manifest.json"] = json.dumps(manifest).encode("utf-8")
        s3.object_map["stories/story-1/plan.json"] = json.dumps(plan).encode("utf-8")

        msg = {
            "Body": '{"job_id":"story-1:chapter:01","story_id":"story-1","job_type":"chapter_generate","payload":{"chapter_number":1}}'
        }

        service.process_message(msg)

        self.assertTrue(any('"job_type": "chapter_generate"' in message["MessageBody"] for message in sqs.messages))
        self.assertFalse(any('"job_type": "chapter_image"' in message["MessageBody"] for message in sqs.messages))

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
