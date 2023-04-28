from store import Store, RedisConfig

# Redis store can save json serializeable objects
store = Store(
    backend="redis", 
    config = RedisConfig(
        host = "localhost", 
        port = 6379
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

# pickle redis and localstore can save complex objects

class Complex():
    def __init__(self, a) -> None:
        self.a = a
    def __eq__ (self, other): # necessary for the equal assert later
        return self.a == other.a

objs = [
    "1",
    True,
    ["some", "list"],
    {"some": {"nested": "dict"}},
    Complex(a = 1)
]

store = Store(
    backend="redis", 
    config = RedisConfig(
        host = "localhost", 
        port = 6379,
        encoding = "pickle"
    )
)

print("Testing pickle redis")
for obj in objs:
    store.set("key", obj)
    out = store.get("key")
    if obj != obj:
        print("failed case", obj)

# local store can save complex objects
store = Store()

print("Testing local store")
for obj in objs:
    store.set("key", obj)
    out = store.get("key")
    if out != obj:
        print("failed case", obj)


