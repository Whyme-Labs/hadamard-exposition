"""Development-only metered entry to the installed pip copy, in an empty venv."""
import json
import os
from pathlib import Path
import runpy
import ssl
import sys
import time

receipt_path, runner_path = map(Path, sys.argv[1:3])
byte_limit, deadline = int(sys.argv[3]), float(sys.argv[4])
arguments = sys.argv[5:]
started = time.monotonic()
read_original = ssl.SSLSocket.read
received = 0
read_calls = 0


def metered_read(self, length=1024, buffer=None):
    global received, read_calls
    if time.monotonic() >= deadline:
        raise RuntimeError("dependency installation deadline exceeded")
    allowance = byte_limit - received
    if allowance <= 0:
        raise RuntimeError("dependency HTTPS receive budget exhausted")
    result = read_original(self, min(length, allowance), buffer)
    count = result if isinstance(result, int) else len(result)
    received += count
    read_calls += 1
    return result


ssl.SSLSocket.read = metered_read
exit_code = 1
try:
    sys.argv = [str(runner_path), *arguments]
    runpy.run_path(str(runner_path), run_name="__main__")
    exit_code = 0
except SystemExit as error:
    exit_code = error.code if isinstance(error.code, int) else (0 if error.code is None else 1)
finally:
    content = {
        "schema_version": "hadamard-dependency-transfer.v1",
        "exit_code": exit_code,
        "elapsed_seconds": time.monotonic() - started,
        "https_received_bytes": received,
        "https_read_calls": read_calls,
        "https_receive_byte_limit": byte_limit,
        "measurement": "SSLSocket.read application-visible decrypted HTTPS bytes; includes response headers and metadata, excludes TLS record overhead",
        "start_monotonic": started,
        "deadline_monotonic": deadline,
        "python_executable": sys.executable,
    }
    with receipt_path.open("x") as stream:
        json.dump(content, stream, indent=2, sort_keys=True)
        stream.write("\n")
sys.exit(exit_code)
