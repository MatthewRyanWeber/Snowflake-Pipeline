"""Progress + ETA reporting for long ingests.

Given a known total, renders a bar with percent, throughput, and estimated time remaining:

    patients->PATIENTS_CSV [############------------]  52.0% (1560/3000) 4200 rows/s ETA 0s

If the total is unknown (a source that can't cheaply count), it degrades to a rows-done +
throughput line. Log calls are throttled so a fast load doesn't spam the console.
"""

import logging
import time

logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    if seconds == float("inf"):
        return "?"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class Progress:
    def __init__(self, total, label="load", bar_width=24, min_interval=0.5, clock=time.monotonic):
        self.total = total                 # None if unknown
        self.label = label
        self.bar_width = bar_width
        self.min_interval = min_interval
        self._clock = clock
        self.done = 0
        self.start = clock()
        self._last_log = 0.0

    def update(self, n: int) -> None:
        self.done += n
        now = self._clock()
        if now - self._last_log >= self.min_interval:
            self._last_log = now
            self._emit(now)

    def finish(self) -> None:
        self._emit(self._clock())

    def eta_seconds(self):
        elapsed = self._clock() - self.start
        rate = self.done / elapsed if elapsed > 0 else 0.0
        if not self.total or rate <= 0:
            return float("inf")
        return max(0, self.total - self.done) / rate

    def _emit(self, now: float) -> None:
        elapsed = now - self.start
        rate = self.done / elapsed if elapsed > 0 else 0.0
        if self.total:
            pct = min(100.0, 100.0 * self.done / self.total)
            filled = min(self.bar_width, int(self.bar_width * self.done / self.total))
            bar = "#" * filled + "-" * (self.bar_width - filled)
            logger.info("%s [%s] %5.1f%% (%d/%d) %.0f rows/s ETA %s",
                        self.label, bar, pct, self.done, self.total, rate,
                        format_duration(self.eta_seconds()))
        else:
            logger.info("%s %d rows, %.0f rows/s, %s elapsed",
                        self.label, self.done, rate, format_duration(elapsed))
