FROM python:3.8-slim-buster

WORKDIR /potassium


ADD ./potassium/requirements.txt ./potassium/requirements.txt

RUN pip install -r ./potassium/requirements.txt

ADD . .

RUN pip install pyright
RUN pyright

# tests are passing copy potassium to exports dir
RUN mkdir /exports && cp -r ./potassium /exports/potassium

