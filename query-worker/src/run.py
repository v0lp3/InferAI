import json
import logging
import google.generativeai as genai

from time import sleep, time
from definitions import GEMINI_TOKEN, INSTRUCTION, RABBITMQ_CREDENTIALS, Error
from pika import (
    BasicProperties,
    BlockingConnection,
    ConnectionParameters,
    PlainCredentials,
)
from pika.channel import Channel
from pika.spec import Basic, BasicProperties

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(module)s %(funcName)s %(message)s",
)

genai.configure(api_key=GEMINI_TOKEN)


errors = Error(0, 0)


def query_gemini(ch: Channel, method: Basic.Deliver, _: BasicProperties, body: bytes):
    global errors

    message = json.loads(body)
    timestamp = int(time())

    logging.info(f"Received message: {message}")

    if errors.count > 5 and errors.timestamp - timestamp < 60 * 10:
        logging.info(f"Too many errors, sleeping for now")
        sleep(60)
        return

    try:
        response = model.generate_content(
            INSTRUCTION + "\n```c\n" + message["prompt"] + "```"
        )

        errors = Error(0, timestamp)

        to_ack = True

        try:
            message["response"] = response.text.split("```c\n")[1].split("```")[0]

            ch.basic_publish(
                exchange="",
                routing_key="patching",
                body=json.dumps(message),
                properties=BasicProperties(
                    delivery_mode=2,
                ),
            )

        except:
            logging.info(f"Failed to generate a response for {message}")
            to_ack = False

        sleep(5)

        if to_ack:
            ch.basic_ack(delivery_tag=method.delivery_tag)
    except:
        sleep(15)

        errors = Error(errors.count + 1, timestamp)

        logging.info(f"API error")


model = genai.GenerativeModel("gemini-pro")
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

ch.queue_declare(queue="querying", durable=True, auto_delete=False)

ch.basic_consume(
    queue="querying",
    on_message_callback=query_gemini,
)

ch.start_consuming()
