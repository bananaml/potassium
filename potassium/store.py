import time
import os
from typing import Union
import shelve
from threading import Thread, Lock
import atexit
import redis
import boto3
import pickle
import json


class Entry():
    def __init__(self, value, expiration):
        self.value = value
        self.expiration = expiration


class RedisConfig():
    def __init__(self, host: str, port: str, username: str = None, password: str = None, db: int = 0, encoding: str = "json"):
        "encoding can be 'json' or 'pickle'. JSON is default.\nPickle has better support for arbitrary python types, but using pickle with a remote redis introduces a large security risk, see https://stackoverflow.com/questions/2259270/pickle-or-json/2259351#2259351"
        # validate args
        encodings = ["json", "pickle"]
        if encoding not in encodings:
            raise ValueError(
                "redis config encoding must be one of the following:", encodings)

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db = db
        self.encoding = encoding


class S3Config():
    def __init__(self, aws_access_key_id, aws_secret_access_key, bucket, encoding: str = "json"):
        "encoding can be 'json' or 'pickle'. JSON is default.\nPickle has better support for arbitrary python types, but using pickle across the network to s3 introduces a large security risk, see https://stackoverflow.com/questions/2259270/pickle-or-json/2259351#2259351"
        # validate args
        encodings = ["json", "pickle"]
        if encoding not in encodings:
            raise ValueError(
                "s3 config encoding must be one of the following:", encodings)

        if aws_access_key_id is None:
            raise ValueError(
                "aws_access_key_id must be provided. It is a sensitive key, so ensure it is scoped to the bucket you want to use and not hardcoded in any open source repos.")
        if aws_secret_access_key is None:
            raise ValueError(
                "aws_secret_access_key must be provided. It is a sensitive key, so ensure it is scoped to the bucket you want to use and not hardcoded in any open source repos.")

        self.access_key = aws_access_key_id
        self.secret_access_key = aws_secret_access_key
        self.bucket = bucket
        self.encoding = encoding


class Store():
    def __init__(self, backend: str = "redis", config: Union[None, RedisConfig, S3Config] = None):
        # validate args
        backends = ["redis", "s3"]
        if backend not in backends:
            raise ValueError("backend must be one of the following:", backends)

        self.backend = backend
        self.config = config

        if self.backend == "redis":
            if not isinstance(config, RedisConfig):
                raise ValueError("redis backends require users to bring their own redis, and configure the potassium store to use it with the config argument. For example, to use a local redis, create store with:\n\nfrom potassium.store import Store, RedisConfig\nstore = Store(backend = 'redis', config = RedisConfig(host = 'localhost', port = 6379))")
            self._redis_client = redis.Redis(
                host=config.host,
                port=config.port,
                username=config.username,
                password=config.password,
                db=config.db,
            )

        if self.backend == "s3":
            if not isinstance(config, S3Config):
                raise ValueError("s3 backends require users to bring their own s3 bucket, and configure the potassium store to use it with the config argument. For example, create store with:\n\nfrom potassium.store import Store, S3Config\nstore = Store(backend = 's3', config = S3Config(access_key, secret_access_key, bucket)")
            session = boto3.Session(
                aws_access_key_id=config.access_key,
                aws_secret_access_key=config.secret_access_key
            )
            self._s3_client = session.client('s3')
            self._s3_bucket = config.bucket

    def get(self, key: str):
        if self.backend == "redis":
            encoded = self._redis_client.get(key)
            if encoded == None:
                return None
            if self.config.encoding == "json":
                return json.loads(encoded)
            if self.config.encoding == "pickle":
                return pickle.loads(encoded)

        if self.backend == "s3":
            response = self._s3_client.get_object(
                Bucket=self._s3_bucket, Key=key)
            encoded = response['Body'].read()
            if encoded == None:
                return None
            if self.config.encoding == "json":
                return json.loads(encoded.decode('utf-8'))
            if self.config.encoding == "pickle":
                return pickle.loads(encoded)

    def set(self, key, value, ttl=600):
        if self.backend == "redis":
            if self.config.encoding == "json":
                encoded = json.dumps(value)
            if self.config.encoding == "pickle":
                encoded = pickle.dumps(value)
            self._redis_client.set(key, encoded, ex=ttl)

        if self.backend == "s3":
            if self.config.encoding == "json":
                encoded = json.dumps(value)
            if self.config.encoding == "pickle":
                encoded = pickle.dumps(value)
            self._s3_client.put_object(
                Body=encoded, Bucket=self._s3_bucket, Key=key)
