import argparse
import socket
import time


def wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Wait until a TCP port accepts connections.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()

    return 0 if wait_for_port(args.host, args.port, args.timeout) else 1


if __name__ == "__main__":
    raise SystemExit(main())
