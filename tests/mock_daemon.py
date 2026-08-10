#!/usr/bin/env python3
"""Mock whisplay-daemon implementing the v1 protocol for tests.

Usage: python3 tests/mock_daemon.py <socket_path> <framebuffer_path>

Serves the daemon socket, answers all commands, and scripts a session
against the connected app: button press (1s hold), release, then an exit
request. Every received command is logged to stdout as `MOCK <cmd> ...`
so a test harness can assert the protocol flow.
"""
import json
import os
import socket
import sys
import threading
import time

SOCK = sys.argv[1]
FB_PATH = sys.argv[2]
WIDTH, HEIGHT, STRIDE = 240, 280, 480

subscribers = []
log_lock = threading.Lock()


def log(kind, payload=None):
    with log_lock:
        print("MOCK %s %s" % (kind, json.dumps(payload or {})), flush=True)


def handle(conn):
    reader = conn.makefile("r")
    line = reader.readline().strip()
    if not line:
        conn.close()
        return
    req = json.loads(line)
    cmd, payload = req.get("cmd"), req.get("payload", {})
    log(cmd, payload)

    def reply(obj):
        conn.sendall((json.dumps(obj) + "\n").encode())

    if cmd == "events.subscribe":
        reply({"ok": True, "payload": {}})
        subscribers.append(conn)
        return  # keep the event stream open
    if cmd == "app.focus.acquire":
        reply({"ok": True, "payload": {"app_id": payload.get("app_id"),
                                        "session_token": "tok-1"}})
    elif cmd == "framebuffer.acquire":
        with open(FB_PATH, "wb") as f:
            f.write(b"\x00" * (STRIDE * HEIGHT))
        reply({"ok": True, "payload": {
            "app_id": payload.get("app_id"), "session_token": "tok-1",
            "width": WIDTH, "height": HEIGHT, "stride": STRIDE,
            "pixel_format": "RGB565", "buffer_handle": FB_PATH}})
    else:
        reply({"ok": True, "payload": {}})
    conn.close()


def send_event(name):
    log("EVENT->" + name)
    data = (json.dumps({"event": name, "payload": {}}) + "\n").encode()
    for conn in list(subscribers):
        try:
            conn.sendall(data)
        except Exception:
            subscribers.remove(conn)


def script():
    time.sleep(2.0)
    send_event("button_pressed")
    time.sleep(1.0)
    send_event("button_released")
    time.sleep(3.0)
    send_event("app_exit_requested")


if os.path.exists(SOCK):
    os.unlink(SOCK)
server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(SOCK)
server.listen(8)
threading.Thread(target=script, daemon=True).start()
log("READY")
while True:
    conn, _ = server.accept()
    threading.Thread(target=handle, args=(conn,), daemon=True).start()
