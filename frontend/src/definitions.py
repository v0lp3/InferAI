from os import environ

rabbitmq_pass_filepath = environ.get("RABBITMQ_DEFAULT_PASS_FILE")
flask_secret_key_filepath = environ.get("FLASK_SECRET_KEY_FILE")

with open(rabbitmq_pass_filepath, "r") as f:
    RABBITMQ_PASSWORD = f.read().strip()

with open(flask_secret_key_filepath, "r") as f:
    FLASK_SECRET_KEY = f.read().strip()

RABBITMQ_CREDENTIALS = (environ.get("RABBITMQ_USER", "user"), RABBITMQ_PASSWORD)
