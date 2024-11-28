import json
import logging
import os

import git

from pika import (
    BasicProperties,
    BlockingConnection,
    ConnectionParameters,
    PlainCredentials,
)
from pika.channel import Channel
from pika.spec import Basic, BasicProperties

from contextualizer import ContextParser
from definitions import (
    RABBITMQ_CREDENTIALS,
    STATUS_NO_VULN_FOUND,
    STATUS_REPO_NOT_FOUND,
    STATUS_OK,
)
from infer import Infer, InferReport

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s",
)


def analyze(
    ch: Channel, method: Basic.Deliver, _: BasicProperties, body: bytes
) -> None:
    """
    Callback function for processing messages from the `analyze-jobs` queue.

    This function handles messages containing information about a repository to analyze.
    It clones the repository, runs the Infer analyzer to detect vulnerabilities, processes
    the results to group vulnerabilities by procedure, and sends the analysis data to
    the `query-jobs` queue for further processing.
    """
    message: dict = json.loads(body)
    logging.info(f"Received message: {message}")

    id, entrypoint, repository = (
        message["id"],
        message["entrypoint"],
        message["repository"],
    )
    download_path = os.path.join("/tmp", "storage", id, "repository")

    os.makedirs(download_path, exist_ok=True)

    if not clone_repository(repository, download_path, message):
        msg = {
            "id": id,
            "status": STATUS_REPO_NOT_FOUND,
        }

        ch.basic_publish(
            routing_key="patch-jobs",
            exchange="",
            body=json.dumps(msg),
        )

        ch.basic_ack(delivery_tag=method.delivery_tag)

        return

    vulnerabilities = run_infer_analyzer(download_path, entrypoint, message)
    if not vulnerabilities:
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    ContextParser.update_procedures_line(vulnerabilities)
    unique_procedures = set(
        (vuln.source_path, vuln.procedure_line) for vuln in vulnerabilities
    )
    if len(unique_procedures) > 0:

        for procedure in unique_procedures:
            process_vulnerabilities(ch, id, procedure, vulnerabilities)
    else:
        msg = {
            "id": id,
            "status": STATUS_NO_VULN_FOUND,
        }

        ch.basic_publish(
            routing_key="patch-jobs",
            exchange="",
            body=json.dumps(msg),
        )

    ch.basic_ack(delivery_tag=method.delivery_tag)


def clone_repository(repository: str, download_path: str, message: dict) -> bool:
    """Clone the given repository to the specified path."""
    try:
        git.Repo.clone_from(repository, to_path=download_path)
        return True
    except Exception as e:
        logging.error(f"Failed to clone {message}, {e}")
        return False


def run_infer_analyzer(
    download_path: str, entrypoint: str, message: dict
) -> list[InferReport]:
    """Run the Infer analyzer and return the vulnerabilities detected."""
    try:
        return Infer.run_analyzer(download_path, entrypoint)
    except Exception as e:
        logging.error(f"Failed to analyze {message}, {e}")
        return []


def process_vulnerabilities(
    ch: Channel, id: str, procedure: tuple, vulnerabilities: list[InferReport]
) -> None:
    """Process and publish vulnerabilities grouped by procedure."""
    source_path, procedure_line = procedure

    inherent_vulnerabilities = sorted(
        (
            vuln
            for vuln in vulnerabilities
            if vuln.source_path == source_path and vuln.procedure_line == procedure_line
        ),
        key=lambda vuln: vuln.line,
        reverse=True,
    )

    vulnerabilities[:] = (
        vuln for vuln in vulnerabilities if vuln not in inherent_vulnerabilities
    )
    prompt = ContextParser.get_prompt(inherent_vulnerabilities)

    data = {
        "id": id,
        "source_path": source_path,
        "prompt": prompt,
        "procedure_line": procedure_line,
        "status": STATUS_OK,
    }

    ch.basic_publish(
        exchange="",
        routing_key="query-jobs",
        body=json.dumps(data),
        properties=BasicProperties(delivery_mode=2),
    )


def create_patch(ch: Channel, method: Basic.Deliver, _: BasicProperties, body: bytes):
    """
    Callback function to process messages from the `patch-jobs` queue.

    This function is triggered when a message is received on the `patch-jobs` queue.
    It processes the message to analyze and handle vulnerabilities, either generating
    a patch or saving the status of the analysis.
    """
    message: dict = json.loads(body)

    logging.info(f"Received message: {message}")

    id: str = message["id"]
    status: int = message["status"]

    analysis_dir = os.path.join("/tmp", "storage", id)

    if status == STATUS_OK:
        source_path: str = message["source_path"]
        procedure_line: str = message["procedure_line"]
        response: str = message["response"]

        patch = ContextParser.get_patch(source_path, procedure_line, response)

        filename = source_path.split("/")[-1]

        patch_dir = os.path.join(analysis_dir, "patchs")

        os.makedirs(patch_dir, exist_ok=True)

        patches_path = os.path.join(patch_dir, f"{filename}_{procedure_line}.patch")

        with open(patches_path, "w") as f:
            f.write(patch)
    else:
        status_dir = os.path.join(analysis_dir, "status")

        with open(status_dir, "w") as f:
            f.write(str(status))

    ch.basic_ack(delivery_tag=method.delivery_tag)


credentials = PlainCredentials(*RABBITMQ_CREDENTIALS)
parameters = ConnectionParameters(
    "rabbitmq",
    credentials=credentials,
    connection_attempts=5,
    retry_delay=15,
    heartbeat=600,
    blocked_connection_timeout=400,
)

cn = BlockingConnection(parameters)
ch = cn.channel(1337)
ch.basic_qos()

ch.queue_declare(queue="analyze-jobs", durable=True, auto_delete=False)

ch.queue_declare(queue="patch-jobs", durable=True, auto_delete=False)

ch.basic_consume(
    queue="analyze-jobs",
    on_message_callback=analyze,
)

ch.basic_consume(
    queue="patch-jobs",
    on_message_callback=create_patch,
)

ch.start_consuming()
