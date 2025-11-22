#!/usr/bin/env python3
import time
from typing import Tuple

class CpuStatus:
    """
    A class to monitor CPU utilization on a Linux system by reading /proc/stat
    and /proc/cpuinfo.

    It provides utilization as a combined percentage (System + User) and
    calculates the total available CPU capacity based on the number of cores.
    """

    def __init__(self):
        """Initializes the core count and the last known CPU stats."""
        # Get the total number of logical cores (capacity) once
        self.core_count = self._get_core_count()
        # The total capacity is 100% per core
        self.max_capacity = self.core_count * 100

        # Store the initial CPU Jiffies for the first calculation
        self._last_cpu_total = 0
        self._last_cpu_work = 0
        self.update_stats() # Populate initial values

    def _get_core_count(self) -> int:
        """Reads /proc/cpuinfo to determine the number of logical cores."""
        try:
            # A simple way to get the core count is to count 'processor' lines
            with open("/proc/cpuinfo", "r") as f:
                return sum(1 for line in f if line.startswith("processor"))
        except FileNotFoundError:
            # Fallback for non-Linux or /proc not available
            print("Warning: /proc/cpuinfo not found. Defaulting to 1 core.")
            return 1
        except Exception as e:
            print(f"Error reading /proc/cpuinfo: {e}. Defaulting to 1 core.")
            return 1

    def _get_current_jiffies(self) -> Tuple[int, int]:
        """
        Reads the first line of /proc/stat and returns (work_jiffies, total_jiffies).
        The first line aggregates all CPU time.
        """
        try:
            with open("/proc/stat", "r") as f:
                # Example: cpu 361732 2320 188820 4539118 7050 0 100 0 0 0
                line = f.readline().split()
                if not line or line[0] != 'cpu':
                    raise ValueError("Invalid format in /proc/stat")

                # Jiffies are typically in units of 1/100th of a second.
                # user (1), nice (2), system (3), idle (4), iowait (5), irq (6), softirq (7), steal (8), guest (9), guest_nice (10)
                # Work Jiffies = user + nice + system + irq + softirq + steal
                # Total Jiffies = sum of all fields (from index 1 onwards)

                work_jiffies = sum(int(line[i]) for i in [1, 2, 3, 6, 7, 8])
                total_jiffies = sum(int(line[i]) for i in range(1, len(line)))

                return work_jiffies, total_jiffies
        except Exception as e:
            # Raise if /proc/stat is unreadable or malformed
            raise RuntimeError(f"Failed to read CPU stats from /proc/stat: {e}")

    def update_stats(self, sleep_time: float = 0.0) -> int:
        """
        Calculates the CPU utilization percentage since the last call.
        This requires reading /proc/stat twice with a short delay.

        Args:
            sleep_time (float): Time to pause between readings.

        Returns:
            int: The calculated total CPU usage percentage (0-MaxCapacity).
        """
        # --- First Reading ---
        work_jiffies_1, total_jiffies_1 = self._get_current_jiffies()

        # Wait a short period to get a meaningful delta
        if sleep_time > 0.0:
            time.sleep(sleep_time)

        # --- Second Reading ---
        work_jiffies_2, total_jiffies_2 = self._get_current_jiffies()

        # --- Calculation ---
        # The first time this runs, we can't calculate a delta, so we use the stored
        # previous values. For the very first call in __init__, delta_total will be 0,
        # so we set usage to 0 and ensure the next call works.
        delta_total = total_jiffies_2 - self._last_cpu_total
        delta_work = work_jiffies_2 - self._last_cpu_work

        # Update the stored values for the *next* calculation
        self._last_cpu_total = total_jiffies_2
        self._last_cpu_work = work_jiffies_2

        # If it's the first run, or if the time delta was too small (unlikely)
        if delta_total == 0:
            self._current_usage = 0
            return 0

        # Usage formula: (change_in_work_time / change_in_total_time) * 100 * core_count
        # We multiply by core_count * 100 to get a value that can exceed 100%
        # The result is the percentage of total capacity being used (e.g., 300% on an 800% max system)
        raw_usage = (delta_work / delta_total) * 100 * self.core_count

        # Cap the usage at max capacity (shouldn't happen, but good practice)
        self._current_usage = min(round(raw_usage), self.max_capacity)

        return self._current_usage

    def get_status_string(self) -> str:
        """
        Returns the CPU status in the desired 'CPU=Used/Max%' format.

        Returns:
            str: e.g., 'CPU=300/800%'
        """
        return f"CPU={self._current_usage}/{self.max_capacity}%"

    @property
    def usage_percent(self) -> int:
        """Returns the last calculated usage percentage."""
        return self._current_usage

    @property
    def capacity(self) -> int:
        """Returns the total capacity in percent (cores * 100)."""
        return self.max_capacity

# --- Example Usage ---
if __name__ == "__main__":
    cpu_monitor = CpuStatus()
    print(f"Total logical cores: {cpu_monitor.core_count}")
    print(f"Max CPU Capacity: {cpu_monitor.capacity}%")
    print("-" * 25)

    # Note: The first call after init might show 0% if the sleep in __init__
    # was too short, but the subsequent loop will be accurate.

    for i in range(5):
        # The update_stats method performs the required sleep to calculate the delta
        cpu_monitor.update_stats(sleep_time=0.5)
        print(f"Status {i+1}: {cpu_monitor.get_status_string()} (Raw: {cpu_monitor.usage_percent}%)")
        # In a real script, you'd only call update_stats when you need the new value
        # and likely rely on the sleep_time inside the method to set your refresh rate.

