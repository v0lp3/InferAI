from os import environ

rabbitmq_pass_filepath = environ.get("RABBITMQ_DEFAULT_PASS_FILE")

with open(rabbitmq_pass_filepath, "r") as f:
    RABBITMQ_PASSWORD = f.read().strip()

RABBITMQ_CREDENTIALS = (environ.get("RABBITMQ_USER", "user"), RABBITMQ_PASSWORD)

STATUS_NO_VULN_FOUND = 201
STATUS_REPO_NOT_FOUND = 404
STATUS_OK = 200
