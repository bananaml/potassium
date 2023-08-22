FROM python:3.8-slim-buster

WORKDIR /potassium

ADD . .

RUN pip install -r ./potassium/requirements.txt

RUN pip install pyright
RUN pyright

# tests are passing copy potassium to exports dir
RUN mkdir /exports && cp -r ./potassium /exports/potassium

