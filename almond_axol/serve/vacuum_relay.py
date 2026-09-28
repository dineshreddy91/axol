"""LCUS-2 commands for the left-arm vacuum tool; no robot motor access.

State is the last successfully written command, not pressure feedback.
"""

import fcntl
import os
import termios
import threading
import time


class VacuumRelay:
    def __init__(self, device="/dev/ttyUSB0", writer=None):
        self.device = device
        self._writer = writer or self._write_serial
        self._lock = threading.Lock()
        self.commanded_on = None
        self.error = None

    @staticmethod
    def frame(channel, on):
        if channel not in (1, 2) or type(on) is not bool:
            raise ValueError("Expected channel 1 or 2 and a boolean state")
        state = int(on)
        return bytes((0xA0, channel, state, 0xA0 + channel + state))

    def _write_serial(self, states):
        fd = os.open(self.device, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            attrs = termios.tcgetattr(fd)
            attrs[:4] = [0, 0, termios.CS8 | termios.CREAD | termios.CLOCAL, 0]
            attrs[4:6] = [termios.B9600, termios.B9600]
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            for channel, on in states:
                data = self.frame(channel, on)
                if os.write(fd, data) != len(data):
                    raise OSError("Incomplete relay write")
                termios.tcdrain(fd)
                time.sleep(0.05)
        finally:
            os.close(fd)

    def set(self, on):
        if type(on) is not bool:
            raise ValueError("Suction state must be boolean")
        with self._lock:
            # Never energize vacuum with the vent enabled. On OFF, remove
            # vacuum first. No blow-off pulse is needed for a simple toggle.
            states = [(1, False), (2, True)] if on else [(2, False), (1, False)]
            try:
                self._writer(states)
            except Exception as exc:
                self.commanded_on = None
                self.error = str(exc)
                raise
            self.commanded_on = on
            self.error = None
            return self._status()

    def _status(self):
        return {
            "commanded_on": self.commanded_on,
            "error": self.error,
            "feedback_available": False,
            "device": self.device,
        }

    def release(self):
        """Stop vacuum, pulse the vent for 0.4s, then leave both relays off."""
        with self._lock:
            try:
                try:
                    self._writer([(2, False), (1, True)])
                    time.sleep(0.4)
                finally:
                    # Attempt cleanup even after an incomplete write or interruption.
                    self._writer([(2, False), (1, False)])
            except Exception as exc:
                self.commanded_on = None
                self.error = str(exc)
                raise
            self.commanded_on = False
            self.error = None
            return self._status()

    def status(self):
        with self._lock:
            return self._status()
