import boto3

from ml.worker.config import AWS_REGION, DDB_TABLE_NAME


class AwsClients:
    def __init__(self, session=None):
        self.session = session or boto3.Session(region_name=AWS_REGION)
        self.sqs = self.session.client("sqs")
        self.s3 = self.session.client("s3")
        dynamodb = self.session.resource("dynamodb")
        self.stories_table = dynamodb.Table(DDB_TABLE_NAME)
