FROM debian:bullseye-slim

RUN apt-get update && \
    mkdir -p /usr/share/man/man1 && \
    apt-get install --yes --no-install-recommends \
      curl \
      libc6-dev \
      openjdk-11-jdk-headless \
      sqlite3 \
      xz-utils \
      zlib1g-dev \
      python3 \
      python3-pip \
      gcc \
      git \
      openssh-client

RUN INFER_VERSION=v1.1.0; \
    cd /opt && \
    curl -sL \
      https://github.com/facebook/infer/releases/download/${INFER_VERSION}/infer-linux64-${INFER_VERSION}.tar.xz | \
    tar xJ && \
    rm -f /infer && \
    ln -s ${PWD}/infer-linux64-$INFER_VERSION /infer

WORKDIR /infer-worker
  
COPY requirements.txt .
RUN pip install -r requirements.txt

ENV PATH /infer/bin:${PATH}

COPY . .

CMD ["python3", "/infer-worker/src/run.py"]
