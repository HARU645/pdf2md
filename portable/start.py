# -*- coding: utf-8 -*-
"""Open the screen, on this computer only.

A copy on a memory stick lands on computers this one knows nothing about, so
nothing here is fixed in advance: the folder is wherever this file sits, and
the port is whichever one happens to be free.  The server listens on the
loopback address alone, so the screen exists for the person sitting here and
for nobody else on the network.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


def free_port() -> int:
    """A port nothing else is using.  Asking for port 0 makes the system pick
    one, which beats guessing a number some other program may already hold."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def answering(port, deadline) -> bool:
    """Wait until the server picks up.  Reading a folder of libraries off a
    memory stick is slow, so the first run can take a while."""
    while time.time() < deadline:
        with socket.socket() as sock:
            sock.settimeout(0.4)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.4)
    return False


def main() -> int:
    env = dict(os.environ)
    env["PDF2MD_LOCAL_ONLY"] = "1"      # no door onto the outside, so no lock
    port = free_port()
    url = "http://127.0.0.1:%d" % port
    print("pdf2md 를 시작합니다.  주소: " + url, flush=True)
    print("처음 켤 때는 시간이 좀 걸립니다. 이 창을 닫으면 앱이 꺼집니다.\n", flush=True)

    # Headless, and the browser is opened here instead.  Left to itself the
    # server asks for an email address on a computer it has not run on before,
    # and then waits for an answer a double-clicked window will never give.
    app = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", os.path.join(HERE, "app.py"),
         "--server.port", str(port),
         "--server.address", "127.0.0.1",     # this computer, nobody else
         "--server.headless", "true",
         "--browser.gatherUsageStats", "false"],
        cwd=HERE, env=env)

    if answering(port, time.time() + 180):
        webbrowser.open(url)
    else:
        print("앱이 시작되지 않았습니다.", flush=True)
    return app.wait()


if __name__ == "__main__":
    raise SystemExit(main())
