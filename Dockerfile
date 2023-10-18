FROM python:3.8-slim-buster

ENV NODE_MAJOR=20
RUN apt-get update && \
    apt-get install -y ca-certificates curl gnupg && \
    mkdir -p /etc/apt/keyrings && \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_$NODE_MAJOR.x nodistro main" | tee /etc/apt/sources.list.d/nodesource.list && \
    apt-get update && \
    apt-get install nodejs -y

WORKDIR /potassium

RUN pip install pyright pytest

ADD ./potassium/requirements.txt ./potassium/requirements.txt

RUN pip install -r ./potassium/requirements.txt

ADD . .

RUN pyright
RUN pytest tests

# tests are passing copy potassium to exports dir
RUN mkdir /exports && cp -r ./potassium /exports/potassium

