#!/bin/sh
# Starts a virtual X server for Playwright's headed Chromium, then execs main.py.
#
# We do NOT use `xvfb-run` here: its readiness handshake waits for Xvfb to
# deliver SIGUSR1 to the wrapper shell, and that signal never arrives inside
# this container (a known class of issue when a shell script runs as PID 1) -
# `xvfb-run` hangs forever at that `wait` and main.py is never actually
# started. Confirmed by `docker top` showing only xvfb-run/Xvfb processes,
# and by `docker logs` staying empty even for a plain `python -c "print(...)"`
# wrapped the same way. Starting Xvfb directly and polling for its socket
# file sidesteps the broken handshake entirely.
set -e

DISPLAY_NUM=99
export DISPLAY=":${DISPLAY_NUM}"

# On a `docker restart` (as opposed to a full recreate) the container's
# writable /tmp survives, so a lock/socket left behind by the previous Xvfb
# process is still there. Xvfb then refuses to bind ("Server is already
# active for display 99") and dies immediately - but the readiness check
# below only polls for the socket *file*, which already exists as a stale
# leftover, so it reports ready right away even though nothing is actually
# listening. Every Chromium launch after that silently fails with "Missing
# X server or $DISPLAY" against the dead socket. Clearing both files first
# guarantees this boot's Xvfb always starts clean.
rm -f "/tmp/.X${DISPLAY_NUM}-lock" "/tmp/.X11-unix/X${DISPLAY_NUM}"

Xvfb "${DISPLAY}" -screen 0 1920x1080x24 -nolisten tcp &
XVFB_PID=$!

echo "Waiting for Xvfb (pid ${XVFB_PID}) on display ${DISPLAY}..."
i=0
while [ ! -e "/tmp/.X11-unix/X${DISPLAY_NUM}" ]; do
    i=$((i + 1))
    if [ "$i" -ge 30 ]; then
        echo "Xvfb did not become ready after 15s - exiting." >&2
        exit 1
    fi
    if ! kill -0 "$XVFB_PID" 2>/dev/null; then
        echo "Xvfb process died unexpectedly." >&2
        exit 1
    fi
    sleep 0.5
done
echo "Xvfb ready on ${DISPLAY}."

# exec replaces this shell with python (PID 1), so signals (docker stop) and
# stdio (docker logs) go directly to/from the app instead of through a shell.
exec python main.py
