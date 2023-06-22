import os
from store import Store, RedisConfig, S3Config

# Redis store can save json serializeable objects
store = Store(
    backend="redis",
    config=RedisConfig(
        host="localhost",
        port=6379
    )
)

objs = [
    "1",
    True,
    ["some", "list"],
    {"some": {"nested": "dict"}}
]

print("Testing json redis")
for obj in objs:
    store.set("key", obj)
    out = store.get("key")
    if out != obj:
        print("failed case", obj)

# ----

# pickle redis can save complex objects


class Complex():
    def __init__(self, a) -> None:
        self.a = a

    def __eq__(self, other):  # necessary for the equal assert later
        return self.a == other.a


objs = [
    "1",
    True,
    ["some", "list"],
    {"some": {"nested": "dict"}},
    Complex(a=1)
]

store = Store(
    backend="redis",
    config=RedisConfig(
        host="localhost",
        port=6379,
        encoding="pickle"
    )
)

print("Testing pickle redis")
for obj in objs:
    store.set("key", obj)
    out = store.get("key")
    if obj != obj:
        print("failed case", obj)


# ----


# s3
aws_access_key_id = os.environ["AWS_ACCESS_KEY_ID"]
aws_secret_access_key = os.environ["AWS_SECRET_ACCESS_KEY"]
bucket = "potassium-test"


# s3 store can save json serializeable objects
store = Store(
    backend="s3",
    config=S3Config(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        bucket=bucket,
    )
)

objs = [
    "1",
    True,
    ["some", "list"],
    {"some": {"nested": "dict"}}
]

print("Testing json redis")
for obj in objs:
    store.set("key", obj)
    out = store.get("key")
    if out != obj:
        print("failed case", obj)

# ----

# pickle s3 can save complex objects


class Complex():
    def __init__(self, a) -> None:
        self.a = a

    def __eq__(self, other):  # necessary for the equal assert later
        return self.a == other.a


objs = [
    "1",
    True,
    ["some", "list"],
    {"some": {"nested": "dict"}},
    Complex(a=1)
]

store = Store(
    backend="s3",
    config=S3Config(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
        bucket=bucket,
        encoding="pickle"
    )
)

print("Testing pickle redis")
for obj in objs:
    store.set("key", obj)
    out = store.get("key")
    if obj != obj:
        print("failed case", obj)
