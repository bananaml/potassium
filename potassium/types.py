from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, Optional, Union, Generator, Optional, Union
import json as jsonlib

class RequestHeaders():
    def __init__(self, headers: Dict[str, str]):
        self._headers = headers

    def __getitem__(self, key):
        if not isinstance(key, str):
            raise KeyError(key)
        key = key.upper().replace("-", "_")
        
        return self._headers[key]

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default

@dataclass
class Request():
    id: str
    headers: RequestHeaders
    json: Dict[str, Any]

ResponseBody = Union[bytes, Generator[bytes, None, None]]
RequestID = str

class Response():
    def __init__(self, status: int = 200, json: Optional[dict] = None, headers: Optional[dict] = None, body: Optional[ResponseBody] = None):
        assert json == None or body == None, "Potassium Response object cannot have both json and body set"


        self.headers = headers if headers != None else {}

        # convert json to body if not None
        if json != None:
            self.body = jsonlib.dumps(json).encode("utf-8")
            self.headers["Content-Type"] = "application/json"
        else:
            self.body = body

        self.status = status

    @property
    def json(self):
        if self.body == None:
            return None
        if type(self.body) == bytes:
            try:
                return jsonlib.loads(self.body.decode("utf-8"))
            except:
                return None
        return None
            
    @json.setter
    def json(self, json):
        self.body = jsonlib.dumps(json).encode("utf-8")
        self.headers["Content-Type"] = "application/json"


