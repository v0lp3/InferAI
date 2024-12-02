FROM python:slim


RUN pip install -q -U groq httpx==0.27.2
RUN pip install pika

WORKDIR /query-worker

COPY . .

CMD ["python3", "/query-worker/src/run.py"]
