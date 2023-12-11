import pytest
from potassium.status import StatusEvent, PotassiumStatus, InvalidStatusEvent
import time

@pytest.mark.parametrize("worker_num", [
    1,
    2,
    4
])
def test_workers_starting(worker_num):
    status = PotassiumStatus.initial(worker_num)
    assert status.num_workers == worker_num
    assert status.num_workers_started == 0
    assert status.gpu_available == False
    status = status.update((StatusEvent.WORKER_STARTED,))

    if worker_num == 1:
        assert status.gpu_available == True
    else:
        assert status.gpu_available == False

    for _ in range(worker_num-1):
        status = status.update((StatusEvent.WORKER_STARTED,))
    assert status.num_workers_started == worker_num
    assert status.gpu_available == True

def test_bad_event():
    status = PotassiumStatus.initial(1)
    with pytest.raises(InvalidStatusEvent):
        status.update(("BAD_EVENT",))

def test_inference_requests_single_worker():
    status = PotassiumStatus.initial(1)
    status = status.update((StatusEvent.WORKER_STARTED,))

    status = status.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
    assert status.num_started_inference_requests == 1
    assert status.num_completed_inference_requests == 0
    assert status.gpu_available == False

    status = status.update((StatusEvent.INFERENCE_START, 0))
    status = status.update((StatusEvent.INFERENCE_END, 0))

    assert status.num_started_inference_requests == 1
    assert status.num_completed_inference_requests == 1
    assert status.sequence_number == 1
    assert status.gpu_available == True

    status = status.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
    assert status.num_started_inference_requests == 2
    status = status.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
    assert status.num_started_inference_requests == 3

    status = status.update((StatusEvent.INFERENCE_START, 1))
    status = status.update((StatusEvent.INFERENCE_END, 1))

    assert status.num_started_inference_requests == 3
    assert status.num_completed_inference_requests == 2
    assert status.sequence_number == 3
    assert status.gpu_available == False

    status = status.update((StatusEvent.INFERENCE_START, 2))
    status = status.update((StatusEvent.INFERENCE_END, 2))

    assert status.num_started_inference_requests == 3
    assert status.num_completed_inference_requests == 3
    assert status.sequence_number == 3
    assert status.gpu_available == True

def test_inference_requests_multiple_workers():
    state = PotassiumStatus.initial(2)

    state = state.update((StatusEvent.WORKER_STARTED,))
    state = state.update((StatusEvent.WORKER_STARTED,))

    assert state.gpu_available == True
    assert state.sequence_number == 0

    state = state.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
    assert state.num_started_inference_requests == 1
    assert state.num_completed_inference_requests == 0
    assert state.gpu_available == True

    state = state.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
    assert state.num_started_inference_requests == 2
    assert state.num_completed_inference_requests == 0
    assert state.gpu_available == False

    state = state.update((StatusEvent.INFERENCE_START, 0))
    state = state.update((StatusEvent.INFERENCE_END, 0))

    assert state.num_started_inference_requests == 2
    assert state.num_completed_inference_requests == 1
    assert state.sequence_number == 2
    assert state.gpu_available == True

    state = state.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))
    state = state.update((StatusEvent.INFERENCE_REQUEST_RECEIVED,))

    assert state.num_started_inference_requests == 4
    assert state.num_completed_inference_requests == 1
    assert state.sequence_number == 4
    assert state.gpu_available == False

    state = state.update((StatusEvent.INFERENCE_START, 1))
    state = state.update((StatusEvent.INFERENCE_END, 1))

    assert state.num_started_inference_requests == 4
    assert state.num_completed_inference_requests == 2
    assert state.sequence_number == 4
    assert state.gpu_available == False

    state = state.update((StatusEvent.INFERENCE_START, 2))
    state = state.update((StatusEvent.INFERENCE_END, 2))

    assert state.num_started_inference_requests == 4
    assert state.num_completed_inference_requests == 3
    assert state.sequence_number == 4
    assert state.gpu_available == True

    state = state.update((StatusEvent.INFERENCE_START, 3))
    state = state.update((StatusEvent.INFERENCE_END, 3))

    assert state.num_started_inference_requests == 4
    assert state.num_completed_inference_requests == 4
    assert state.sequence_number == 4
    assert state.gpu_available == True

@pytest.mark.parametrize("status_result_tuple", [
    (PotassiumStatus(
        num_started_inference_requests=0,
        num_completed_inference_requests=0,
        num_bad_requests=0,
        num_workers=1,
        num_workers_started=0,
        idle_start_timestamp=0,
        in_flight_request_start_times=[]
    ), 0),
    (PotassiumStatus(
        num_started_inference_requests=0,
        num_completed_inference_requests=0,
        num_bad_requests=0,
        num_workers=1,
        num_workers_started=1,
        idle_start_timestamp=0,
        in_flight_request_start_times=[]
    ), time.time()),
    (PotassiumStatus(
        num_started_inference_requests=1,
        num_completed_inference_requests=0,
        num_bad_requests=0,
        num_workers=1,
        num_workers_started=1,
        idle_start_timestamp=0,
        in_flight_request_start_times=[]
    ), 0),
    (PotassiumStatus(
        num_started_inference_requests=2,
        num_completed_inference_requests=0,
        num_bad_requests=0,
        num_workers=4,
        num_workers_started=4,
        idle_start_timestamp=0,
        in_flight_request_start_times=[]
    ), 0),
    (PotassiumStatus(
        num_started_inference_requests=2,
        num_completed_inference_requests=2,
        num_bad_requests=0,
        num_workers=4,
        num_workers_started=4,
        idle_start_timestamp=0,
        in_flight_request_start_times=[]
    ), time.time()),
])
def test_idle_time(status_result_tuple):
    status, result = status_result_tuple
    delta = abs(status.idle_time - result)
    ALLOWED_DELTA = 1
    assert delta < ALLOWED_DELTA

def test_longest_inference_time():
    status = PotassiumStatus(
        num_started_inference_requests=6,
        num_completed_inference_requests=2,
        num_bad_requests=0,
        num_workers=4,
        num_workers_started=4,
        idle_start_timestamp=0,
        in_flight_request_start_times=[
            ("b", time.time() - 2),
            ("a", time.time() - 1),
            ("c", time.time() - 3),
            ("d", time.time()),
        ]
    )

    longest_inference_time = status.longest_inference_time
    EXPECTED_LONGEST_INFERENCE_TIME = 3
    delta = abs(longest_inference_time - EXPECTED_LONGEST_INFERENCE_TIME)

    ALLOWED_DELTA = 0.1
    assert delta < ALLOWED_DELTA




