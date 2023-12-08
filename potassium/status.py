from enum import Enum
import time
from typing import List, Tuple
from dataclasses import dataclass

from .types import RequestID

class StatusEvent(Enum):
    INFERENCE_REQUEST_RECEIVED = "INFERENCE_REQUEST_RECEIVED"
    INFERENCE_START = "INFERENCE_START"
    INFERENCE_END = "INFERENCE_END"
    WORKER_STARTED = "WORKER_STARTED"
    BAD_REQUEST_RECEIVED = "BAD_REQUEST_RECEIVED"

@dataclass
class PotassiumStatus():
    """PotassiumStatus is a simple class that represents the status of a Potassium app."""
    num_started_inference_requests: int
    num_completed_inference_requests: int
    num_bad_requests: int
    num_workers: int
    num_workers_started: int
    idle_start_timestamp: float
    in_flight_request_start_times: List[Tuple[RequestID, float]]

    @property
    def requests_in_progress(self):
        return self.num_started_inference_requests - self.num_completed_inference_requests

    @property
    def gpu_available(self):
        return self.num_workers - self.requests_in_progress > 0

    @property
    def sequence_number(self):
        return self.num_started_inference_requests + self.num_bad_requests

    @property
    def idle_time(self):
        if not self.gpu_available or len(self.in_flight_request_start_times) > 0:
            return 0
        return time.time() - self.idle_start_timestamp

    @property
    def longest_inference_time(self):
        if self.in_flight_request_start_times == []:
            return 0

        oldest_start_time = min([start_time for _, start_time in self.in_flight_request_start_times])

        return time.time() - oldest_start_time

    def update(self, event) -> "PotassiumStatus":
        event_type = event[0]
        event_data = event[1:]
        if event_type not in event_handlers:
            raise Exception(f"Invalid event {event}")
        return event_handlers[event_type](self.clone(), *event_data)


    def clone(self):
        return PotassiumStatus(
            self.num_started_inference_requests,
            self.num_completed_inference_requests,
            self.num_bad_requests,
            self.num_workers,
            self.num_workers_started,
            self.idle_start_timestamp,
            self.in_flight_request_start_times
        )

def handle_start_inference(status: PotassiumStatus, request_id: RequestID):
    status.in_flight_request_start_times.append((request_id, time.time()))
    return status

def handle_end_inference(status: PotassiumStatus, request_id: RequestID):
    status.num_completed_inference_requests += 1
    status.in_flight_request_start_times = [t for t in status.in_flight_request_start_times if t[0] != request_id]

    if status.gpu_available:
        status.idle_start_timestamp = time.time()

    return status

def handle_inference_request_received(status: PotassiumStatus):
    status.num_started_inference_requests += 1
    return status

def handle_worker_started(status: PotassiumStatus):
    status.num_workers_started += 1
    return status

def handle_bad_request_received(status: PotassiumStatus):
    status.num_bad_requests += 1
    return status

event_handlers = {
    StatusEvent.INFERENCE_REQUEST_RECEIVED: handle_inference_request_received,
    StatusEvent.INFERENCE_START: handle_start_inference,
    StatusEvent.INFERENCE_END: handle_end_inference,
    StatusEvent.WORKER_STARTED: handle_worker_started,
    StatusEvent.BAD_REQUEST_RECEIVED: handle_bad_request_received
}


