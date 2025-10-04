# utils.py
import tracemalloc
import sys
import logging

logger = logging.getLogger(__name__)

class Debugger:
    def __init__(self, turnon: bool = False):
        self.turnon = turnon
        if self.turnon:
            tracemalloc.start()
            logger.info("Tracemalloc started.")

    def memory_snapshot(self, message: str, key_type='lineno', limit=10):
        if not self.turnon:
            return

        snapshot = tracemalloc.take_snapshot()
        print(f"\n--- {message} ---")
        
        snapshot = snapshot.filter_traces((
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
            tracemalloc.Filter(False, "utils.py"), # Exclude debugger's own memory
        ))
        top_stats = snapshot.statistics(key_type)

        print(f"Top {limit} lines/objects consuming memory:")
        for index, stat in enumerate(top_stats[:limit]):
            print(f"#{index+1}: {stat.traceback.format(limit=1)[0]}\n    {stat.size / 1024:.1f} KiB")
        total = sum(stat.size for stat in top_stats)
        print(f"Total allocated size: {total / (1024 * 1024):.1f} MiB")
        print("-" * 40)

    def stop(self):
        if self.turnon and tracemalloc.is_tracing():
            tracemalloc.stop()
            logger.info("Tracemalloc stopped.")

