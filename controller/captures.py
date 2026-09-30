"""Fire screenshot capture with a background save worker.

Saving a capture involves a JPEG encode and disk I/O (plus pruning old files),
which would otherwise block the detection loop on the first frame of a fire.
``enqueue_capture`` hands the frame to a background worker so the loop keeps
running; the synchronous helpers remain available for the Flask routes.
"""

import os
import queue
import threading
from datetime import datetime

import cv2

from config import CAPTURE_DIR, CAPTURE_MAX, CAPTURE_QUEUE_MAX


def _capture_dir():
    """Return the absolute path to the capture directory, creating it if needed."""
    path = os.path.abspath(CAPTURE_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def list_captures():
    """Return a list of capture dicts (filename, timestamp), newest first."""
    path = _capture_dir()
    captures = []
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if not os.path.isfile(full) or not name.lower().endswith(".jpg"):
            continue
        try:
            ts = datetime.fromtimestamp(os.path.getmtime(full)).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        except OSError:
            ts = ""
        captures.append({"filename": name, "timestamp": ts})
    captures.sort(key=lambda c: c["filename"], reverse=True)
    return captures


def _enforce_capture_limit():
    """Delete the oldest captures so at most CAPTURE_MAX remain."""
    path = _capture_dir()
    files = sorted(
        (os.path.join(path, name) for name in os.listdir(path)
         if name.lower().endswith(".jpg")),
        key=os.path.getmtime,
    )
    while len(files) > CAPTURE_MAX:
        oldest = files.pop(0)
        try:
            os.remove(oldest)
        except OSError:
            pass


def save_capture(frame):
    """Save an annotated frame as a JPEG capture and enforce the size cap.

    Returns the filename on success, or None on failure.
    """
    if frame is None:
        return None
    path = _capture_dir()
    filename = datetime.now().strftime("%Y%m%d_%H%M%S") + ".jpg"
    full = os.path.join(path, filename)
    # Avoid collisions if two events land in the same second.
    counter = 1
    while os.path.exists(full):
        filename = datetime.now().strftime("%Y%m%d_%H%M%S") + f"_{counter}.jpg"
        full = os.path.join(path, filename)
        counter += 1
    ok, jpeg = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    try:
        with open(full, "wb") as f:
            f.write(jpeg.tobytes())
    except OSError as exc:
        print(f"Failed to save capture: {exc}")
        return None
    _enforce_capture_limit()
    print(f"Saved fire capture: {filename}")
    return filename


def delete_capture(filename):
    """Delete a single capture file. Returns True if it was removed."""
    path = _capture_dir()
    full = os.path.join(path, os.path.basename(filename))
    if not os.path.isfile(full):
        return False
    try:
        os.remove(full)
        return True
    except OSError:
        return False


def clear_captures():
    """Delete all capture files. Returns the number removed."""
    path = _capture_dir()
    removed = 0
    for name in os.listdir(path):
        full = os.path.join(path, name)
        if os.path.isfile(full) and name.lower().endswith(".jpg"):
            try:
                os.remove(full)
                removed += 1
            except OSError:
                pass
    return removed


# ---------------------------------------------------------------------------
# Background capture worker
# ---------------------------------------------------------------------------
_capture_queue = queue.Queue(maxsize=CAPTURE_QUEUE_MAX)
_worker_stop = threading.Event()
_worker_thread = None
_worker_lock = threading.Lock()


def enqueue_capture(frame):
    """Queue a frame for background saving (non-blocking).

    The caller must pass a frame it will not mutate afterwards (the detection
    loop copies its annotated frame before calling this). When the queue is
    full the oldest pending frame is dropped.
    """
    if frame is None:
        return
    try:
        _capture_queue.put_nowait(frame)
    except queue.Full:
        try:
            _capture_queue.get_nowait()
        except queue.Empty:
            pass
        try:
            _capture_queue.put_nowait(frame)
        except queue.Full:
            pass


def _capture_worker_loop():
    """Drain the capture queue, saving frames off the detection loop."""
    while not _worker_stop.is_set():
        try:
            frame = _capture_queue.get(timeout=0.1)
        except queue.Empty:
            continue
        try:
            save_capture(frame)
        except Exception as exc:  # never let the worker die
            print(f"Capture worker error: {exc}")


def start_capture_worker():
    """Start the background capture worker (idempotent)."""
    global _worker_thread
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(
            target=_capture_worker_loop, daemon=True, name="capture-worker",
        )
        _worker_thread.start()


def stop_capture_worker():
    """Stop the background capture worker."""
    global _worker_thread
    with _worker_lock:
        _worker_stop.set()
        if _worker_thread is not None:
            _worker_thread.join(timeout=1.0)
            _worker_thread = None
