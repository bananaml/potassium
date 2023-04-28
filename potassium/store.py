import time, os
from typing import Union
import shelve
from threading import Thread, Lock
import atexit
import redis
import pickle
import json


class Entry():
    def __init__(self, value, expiration):
        self.value = value
        self.expiration = expiration
class RedisConfig():
    def __init__(self, host:str, port:str, username:str = None, password:str = None, db:int = 0, encoding:str = "json"):
        "encoding can be 'json' or 'pickle'. JSON is default.\nPickle has better support for arbitrary python types, but using pickle with a remote redis introduces a large security risk, see https://stackoverflow.com/questions/2259270/pickle-or-json/2259351#2259351"
        # validate args
        encodings = ["json", "pickle"]
        if encoding not in encodings:
            raise ValueError("redis config encoding must be one of the following:", encodings)
        
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.db = db
        self.encoding = encoding
class Store():
    def __init__(self, backend: str ="local", config: Union[None, RedisConfig] = None):
        # validate args
        backends = ["local", "redis"]
        if backend not in backends:
            raise ValueError("backend must be one of the following:", backends)
        
        self.backend = backend
        self.config = config
         
        if self.backend == "local": 
            self._local_store = shelve.open(".localstore")
            self._lock = Lock()
            
            # run TTL gc as thread
            thread = Thread(target=self._gc)
            thread.daemon = True
            thread.start()

            # delete store at exit, to avoid side effects
            def exit_handler():
                os.remove(".localstore")
            atexit.register(exit_handler)

        if self.backend == "redis":
            if not isinstance(config, RedisConfig):
                raise ValueError("redis backends require users to bring their own redis, and configure the potassium store to use it with the config argument. For example, to use a local redis, create store with:\n\nfrom potassium.store import Store, RedisConfig\nstore = Store(backend = 'redis', config = RedisConfig(host = 'localhost', port = 6379))")
            self._redis_store = redis.Redis(
                host=config.host, 
                port=config.port,
                username=config.username,
                password=config.password,
                db=config.db,
            )

    def _gc(self):
        if self.backend == "local":
            while True:
                time.sleep(1)
                with self._lock:
                    try:
                        for k, v in self._local_store.items():
                            if v.expiration < time.time():
                                del self._local_store[k]
                    except:
                        pass

    def get(self, key: str):
        if self.backend == "local":
            with self._lock:
                entry = self._local_store.get(key)
            if entry == None:
                return None
            return entry.value
        
        if self.backend == "redis":
            encoded = self._redis_store.get(key)
            if encoded == None:
                return None
            if self.config.encoding == "json":
                return json.loads(encoded)
            if self.config.encoding == "pickle":
                return pickle.loads(encoded)
    
    def set(self, key, value, ttl=600):
        if self.backend == "local":
            with self._lock:
                self._local_store[key] = Entry(
                    value=value,
                    expiration=time.time()+ttl
                )

        if self.backend == "redis":
            if self.config.encoding == "json":
                encoded = json.dumps(value)
            if self.config.encoding == "pickle":
                encoded = pickle.dumps(value)
            self._redis_store.set(key, encoded, ex=ttl)