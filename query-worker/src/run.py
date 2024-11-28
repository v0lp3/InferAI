import json
import logging

# import google.generativeai as genai
from groq import Groq


from time import sleep, time
from definitions import GROQ_TOKEN, INSTRUCTION, RABBITMQ_CREDENTIALS, Error
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

client = Groq(
    api_key=GROQ_TOKEN,
)

errors = Error(0, 0)


def query_llm(ch: Channel, method: Basic.Deliver, _: BasicProperties, body: bytes):
    global errors

    message = json.loads(body)
    timestamp = int(time())

    logging.info(f"Received message: {message}")

    if errors.count > 5 and errors.timestamp - timestamp < 60 * 10:
        logging.info(f"Too many errors, sleeping for now")
        sleep(60)
        return

    try:
        prompt = INSTRUCTION + "\n```c\n" + message["prompt"] + "```"

        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="llama-3.1-70b-versatile",
        )

        errors = Error(0, timestamp)

        to_ack = True

        try:
            message["response"] = (
                chat_completion.choices[0]
                .message.content.split("```c\n")[1]
                .split("```")[0]
            )
            message["status"] = 200

            ch.basic_publish(
                exchange="",
                routing_key="patch-jobs",
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

ch.queue_declare(queue="query-jobs", durable=True, auto_delete=False)

ch.basic_consume(
    queue="query-jobs",
    on_message_callback=query_llm,
)

ch.start_consuming()
