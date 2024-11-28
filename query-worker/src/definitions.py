from os import environ
from collections import namedtuple

rabbitmq_pass_filepath = environ.get("RABBITMQ_DEFAULT_PASS_FILE")
gemini_token_filepath = environ.get("GEMINI_TOKEN_FILE")
http_proxy_filepath = environ.get("HTTP_PROXY_FILE")

with open(rabbitmq_pass_filepath, "r") as f:
    RABBITMQ_PASSWORD = f.read().strip()

with open(gemini_token_filepath, "r") as f:
    GEMINI_TOKEN = f.read().strip()

with open(http_proxy_filepath, "r") as f:
    proxy = f.read().strip()
    environ["http_proxy"] = proxy

RABBITMQ_CREDENTIALS = (environ.get("RABBITMQ_USER", "user"), RABBITMQ_PASSWORD)

INSTRUCTION = """Task: Replace the suggested [Unsafe] C code function to improve its security.

Output: Return only the modified function as a code block formatted in markdown for C code.

Notes:

- The output must be valid and safe C code and address security vulnerabilities.
- Do not modify the function signature (name and arguments).
"""

Error = namedtuple("Error", ["count", "timestamp"])
