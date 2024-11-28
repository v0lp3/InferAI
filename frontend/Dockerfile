FROM python:3.12.2  

WORKDIR /app

RUN apt update && apt install -y --no-install-recommends \
    git \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "src/app.py"]