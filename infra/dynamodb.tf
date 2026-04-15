####################################
# DynamoDB - BookgenStories
####################################

resource "aws_dynamodb_table" "stories" {
  name         = "BookgenStories"
  billing_mode = "PAY_PER_REQUEST" # pas de coût fixe, parfait pour démarrer
  hash_key     = "story_id"

  attribute {
    name = "story_id"
    type = "S"
  }

  tags = {
    Name    = "BookgenStories"
    Project = "bookgen"
  }
}
