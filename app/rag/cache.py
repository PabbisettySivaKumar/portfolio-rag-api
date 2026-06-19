import threading
import time
from collections import OrderedDict


class SimpleLRUCache:
    def __init__(self, maxsize=200, ttl_seconds=3600):
        self.cache = OrderedDict()
        self.maxsize = maxsize
        self.ttl = ttl_seconds
        self.lock = threading.Lock()

    def get(self, key: str):
        with self.lock:
            if key not in self.cache:
                return None
            val, timestamp = self.cache[key]
            if time.time() - timestamp > self.ttl:
                del self.cache[key]
                return None
            self.cache.move_to_end(key)
            return val

    def set(self, key: str, val) -> None:
        with self.lock:
            if key in self.cache:
                del self.cache[key]
            elif len(self.cache) >= self.maxsize:
                self.cache.popitem(last=False)  # Evict oldest
            self.cache[key] = (val, time.time())


# Global cache instance (200 items maximum, 1 hour TTL)
query_cache = SimpleLRUCache(maxsize=200, ttl_seconds=3600)
