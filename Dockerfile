FROM python:3.8-slim-buster

WORKDIR /potassium

RUN pip install pyright pytest

ADD ./potassium/requirements.txt ./potassium/requirements.txt

RUN pip install -r ./potassium/requirements.txt

ADD . .

RUN pyright
RUN pytest tests

# tests are passing copy potassium to exports dir
RUN mkdir /exports && cp -r ./potassium /exports/potassium

