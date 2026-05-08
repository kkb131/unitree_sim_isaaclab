"""Subscribe to UR10e ZMQ camera ports and report frame count + average JPEG size.

UR10e is single-arm — only ports 55555 (front) and 55557 (right_wrist) are
expected to publish. Port 55556 (left_wrist) is silent by design.

Usage:
    source custom/scripts/activate_env.sh
    python custom/scripts/test_zmq_recv.py [--duration 5.0]
"""

import argparse
import time

import zmq


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--duration", type=float, default=5.0, help="seconds to listen")
    p.add_argument(
        "--ports",
        type=str,
        default="55555:front,55557:right_wrist",
        help='comma-separated "port:label" pairs',
    )
    args = p.parse_args()

    pairs = []
    for entry in args.ports.split(","):
        port_s, label = entry.split(":")
        pairs.append((int(port_s.strip()), label.strip()))

    ctx = zmq.Context()
    subs = []
    counts = {label: 0 for _, label in pairs}
    sizes = {label: 0 for _, label in pairs}
    first_size = {label: None for _, label in pairs}

    for port, label in pairs:
        s = ctx.socket(zmq.SUB)
        s.connect(f"tcp://127.0.0.1:{port}")
        s.setsockopt_string(zmq.SUBSCRIBE, "")
        subs.append((s, label, port))

    poller = zmq.Poller()
    for s, _, _ in subs:
        poller.register(s, zmq.POLLIN)

    print(f"listening on ports {[p for p, _ in pairs]} for {args.duration:.1f}s...")
    t0 = time.time()
    while time.time() - t0 < args.duration:
        events = dict(poller.poll(timeout=100))   # 100 ms
        for s, label, _ in subs:
            if events.get(s) == zmq.POLLIN:
                buf = s.recv()
                counts[label] += 1
                sizes[label] += len(buf)
                if first_size[label] is None:
                    first_size[label] = len(buf)

    for s, _, _ in subs:
        s.close()
    ctx.term()

    print(f"\n=== results ({args.duration:.1f}s) ===")
    overall_pass = True
    for port, label in pairs:
        n = counts[label]
        avg = sizes[label] // n if n else 0
        rate = n / args.duration
        ok = n > 0 and avg > 1024
        overall_pass = overall_pass and ok
        marker = "OK" if ok else "FAIL"
        print(
            f"{label:14s} (port {port}): {n:4d} frames "
            f"({rate:5.1f} Hz), avg {avg:7d} bytes  [{marker}]"
        )
    print(f"\noverall: {'PASS' if overall_pass else 'FAIL'}")


if __name__ == "__main__":
    main()
