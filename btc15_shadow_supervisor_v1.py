"""Restart telemetry children without stopping or changing the signal engine."""
import subprocess
import sys
import time


class ShadowChild:
    def __init__(self, script, clock=time.monotonic, spawn=subprocess.Popen):
        self.script, self.clock, self.spawn = str(script), clock, spawn
        self.process = None
        self.next_start = 0.0
        self.delay = 2.0
        self.started = 0.0
        self.stopped = False
        self.maintain()

    def maintain(self):
        if self.stopped:
            return
        now = self.clock()
        if self.process is not None:
            if self.process.poll() is None:
                if now - self.started >= 60:
                    self.delay = 2.0
                return
            print(f'SHADOW CHILD EXIT | {self.script} | rc={self.process.returncode} | retry={self.delay}s | NO ORDERS', flush=True)
            self.process = None
            self.next_start = now + self.delay
            self.delay = min(30.0, self.delay * 2)
        if now >= self.next_start:
            self.process = self.spawn([sys.executable, '-u', self.script])
            self.started = now

    def stop(self):
        self.stopped = True
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
