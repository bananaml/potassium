import time, os
import shelve
from threading import Thread, Lock
import atexit


class Entry():
    def __init__(self, value, expiration):
        self.value = value
        self.expiration = expiration

class Store():
    def __init__(self, backend="local"):
        self.backend = backend
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
    
    def set(self, key, value, ttl=600):
        if self.backend == "local":
            with self._lock:
                self._local_store[key] = Entry(
                    value=value,
                    expiration=time.time()+ttl
                )