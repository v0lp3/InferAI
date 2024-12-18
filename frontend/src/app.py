import json
import logging
import os.path
import secrets
import zipfile
import jwt

from time import time
from definitions import FLASK_SECRET_KEY, RABBITMQ_CREDENTIALS
from flask import Flask, Response, make_response, render_template, request, send_file
from pika import (
    BasicProperties,
    BlockingConnection,
    ConnectionParameters,
    PlainCredentials,
)
from pika.spec import BasicProperties

app = Flask(__name__, static_folder="../static", template_folder="../templates")


def get_analyzed_files_ids() -> list[str]:
    """
    Retrieves the list of file IDs previously analyzed by the application, stored in a cookie.

    The application uses a JWT stored in the "token" cookie to keep track of file IDs
    that were previously analyzed. This function decodes the JWT and extracts the "ids" field.

    Returns:
        list[str]: A list of file IDs previously analyzed.
                   Returns an empty list if the token is missing or invalid.
    """
    token = request.cookies.get("token")

    try:
        decoded_token: dict = jwt.decode(token, app.secret_key, algorithms=["HS256"])
        return decoded_token["ids"]
    except:
        return []


@app.route("/")
def index() -> str:
    """
    Returns homepage template.
    """
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze() -> Response:
    """
    This function processes POST requests containing repository details and enqueues
    a message to a message broker for asynchronous analysis. It also generates a JWT
    token for tracking analysis IDs and sets it as a cookie.

    Returns:
        Response:
            - A 200 response with the message "Done" if the request is successfully processed.
            - A 400 response with the message "Invalid request" if the request payload is malformed.
    """
    request_data: dict = request.form.to_dict()

    try:
        entrypoint: str = request_data.get("entrypoint", "main.c")
        repository: str = request_data["repository"]
    except:
        return "Invalid request", 400

    id: str = secrets.token_hex(32)

    data: dict = {  # request can contain more data than needed
        "entrypoint": entrypoint,
        "repository": repository,
        "id": id,
    }

    ids: list[str] = get_analyzed_files_ids() + [id]

    token: str = jwt.encode({"ids": ids}, app.secret_key, algorithm="HS256")

    resp: Response = make_response(f"Done. Job: {id}", 200)
    resp.set_cookie("token", token)

    try:
        ch.basic_publish(
            exchange="",
            routing_key="analyze-jobs",
            body=json.dumps(data),
            properties=BasicProperties(
                delivery_mode=2,
            ),
        )

    except Exception as e:
        logging.info(e)
        return "Error", 500

    return resp


@app.route("/patchs", methods=["GET", "POST"])
def view() -> Response:
    """
    Handle requests for the `/patchs` route. Supports both `GET` and `POST` methods.

    - On a `GET` request:
        Renders a template `patchs.html` with a list of available patch IDs for analyzed files.

    - On a `POST` request:
        Processes a form submission containing an `id` to download the patch.

    Returns:
        Response:
            - Renders the `patchs.html` template for `GET` requests.
            - Sends the generated ZIP file as an attachment for valid `POST` requests.
            - Returns a 400 response for invalid IDs.
            - Returns a 500 response if an error occurs during file packaging.
    """
    ids: list[str] = get_analyzed_files_ids()

    if request.method == "GET":
        return render_template("patchs.html", patchs=ids)

    id: str = request.form.get("id")
    only_bug_changelog: bool = bool(request.form.get("only_bug_changelog"))

    if id not in ids:
        return "Invalid request", 400

    job_path = os.path.join("/storage", id)
    patchs_path = os.path.join(job_path, "patchs")
    status_path = os.path.join(job_path, "status")

    if os.path.exists(patchs_path):
        json_files_path = [
            os.path.realpath(os.path.join(job_path, file))
            for file in os.listdir(job_path)
            if file.endswith(".json")
        ]

        if only_bug_changelog:
            changelogs = []

            for file in json_files_path:
                with open(file) as f:
                    changelogs += [json.load(f)]

            return changelogs, 200

        timestamp = int(time())
        output_file = os.path.join("/tmp", f"patchs_{id}_{timestamp}.zip")

        try:
            with zipfile.ZipFile(output_file, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in json_files_path:
                    zipf.write(file, arcname=os.path.basename(file))

                for root, _, files in os.walk(patchs_path):
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, patchs_path)
                        zipf.write(file_path, arcname=arcname)

            return send_file(output_file, as_attachment=True)

        except Exception as e:
            logging.error(f"Error while creating ZIP: {e}")
            return "Error", 500

    if os.path.exists(status_path):
        with open(status_path) as f:
            return f.read(), 200

    return "Analysis in progress", 202


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s",
)

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

if not FLASK_SECRET_KEY:
    app.secret_key = secrets.token_hex(32)
else:
    app.secret_key = FLASK_SECRET_KEY

app.run(host="0.0.0.0", port=5000)
