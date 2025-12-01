#!/usr/bin/env python3
"""
FFmpeg subprocess monitor for non-blocking progress tracking
"""
import os
import re
import fcntl
import subprocess
from typing import Optional, Union

class FfmpegMon:
    """
    Monitors an FFmpeg subprocess non-blockingly.

    Provides a clean .start() and .poll() interface for use in a
    single-threaded interactive loop (like a curses application).
    """

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.partial_line: bytes = b""
        self.output_queue: list[str] = []  # <--- NEW: Queue for complete lines
        self.return_code: Optional[int] = None
        self.temp_file = None

    def start(self, command_line: list[str], temp_file: Optional[str] = None) -> None:
        """
        Starts the FFmpeg subprocess.

        Args:
            command_line: The full FFmpeg command as a list of strings.
            temp_file: Optional path to the temporary output file (for cleanup on stop).
        """
        self.temp_file = temp_file
        if self.process:
            raise RuntimeError("FfmpegMon is already monitoring a process.")

        try:
            # Start the process, piping stderr for progress updates
            self.process = subprocess.Popen(
                command_line,
                stdout=subprocess.DEVNULL,  # Discard normal output
                stderr=subprocess.PIPE,     # Capture progress messages
                text=False,                  # Read output as text
                bufsize=0
            )

            # --- CRITICAL: Make stderr non-blocking ---
            # Get the file descriptor number for the stderr pipe
            fd = self.process.stderr.fileno()
            # Get the current flags
            fl = fcntl.fcntl(fd, fcntl.F_GETFL)
            # Set the O_NONBLOCK flag
            fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        except Exception as e:
            # Handle common errors like 'ffmpeg' not found
            print(f"Error starting FFmpeg process: {e}")
            self.return_code = 127

    def poll(self) -> Union[Optional[int], str]:
        """
        Reads and processes data. Returns the next item from the internal queue
        (string output) or the final return code (integer).
        """
        # --- Stage 0: Process Queue First & Status Check (remains unchanged) ---
        if self.output_queue:
            return self.output_queue.pop(0)

        if not self.process:
            return self.return_code

        process_status = self.process.poll()

        # 1. Read available data non-blockingly
        try:
            chunk = self.process.stderr.read()
        except (IOError, OSError):
            chunk = b""

        # 2. Process NEW DATA
        if chunk:
            # Append the new chunk to the existing buffer
            # We must use bytes for the buffer: self.partial_line + chunk
            data = self.partial_line + chunk

            # --- CRITICAL FIX: Split by EITHER \n OR \r ---
            # We need to split by both, keeping the delimiters for context is not needed,
            # but handling trailing fragments is important.

            # 2a. Split data by \n or \r. Note: re.split discards delimiters.
            # Use 'b' prefix for regex pattern since data is bytes
            fragments = re.split(b'[\r\n]', data)

            # 2b. The last element is the new partial line (may be an empty fragment)
            self.partial_line = fragments[-1]

            # 2c. The rest are complete lines/progress updates
            # We ignore empty strings/fragments that occur from successive delimiters (like \r\n or \n\n).
            for line_bytes in fragments[:-1]:
                if line_bytes: # Ignore empty fragments
                    line_str = line_bytes.decode('utf-8', errors='ignore')
                    self.output_queue.append(line_str)

        # --- Stage 3 & 4: Handle Termination and Final Check (remains largely unchanged) ---
        if process_status is not None:
            # The process is done. Process any remaining data in partial_line.
            if self.partial_line:
                # Decode and add the final output/error line.
                final_output = self.partial_line.decode('utf-8', errors='ignore')
                self.partial_line = b"" # Buffer consumed
                self.output_queue.append(final_output) # Add the final line to the queue

            # If the queue now has items, return the first one.
            if self.output_queue:
                self.return_code = process_status # Store code for *after* the queue is empty
                return self.output_queue.pop(0)

            # If the queue is empty, we return the final code.
            self.return_code = process_status
            self.process = None
            return self.return_code

        # --- Stage 4: Final Check ---
        if self.output_queue:
            return self.output_queue.pop(0)

        return None

    def _read_remaining(self):
        """
        Helper to read any final buffered output after termination.
        """
        # Read all remaining output
        try:
            remaining_data = self.process.stderr.read()
            self.partial_line += remaining_data
        except (IOError, OSError):
            pass # Ignore if stream is already closed or empty

        # Check if the final output contains a full line we missed
        if self.partial_line:
            # This logic is a bit simple, but assumes the final chunk is mostly an error message.
            # You may want to store this in a separate error buffer for later dump.
            # For now, we'll just discard it if it's not a complete line.
            pass

    def stop(self, return_code=255):
        """
        Terminates the subprocess if it is still running.
        """
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=15) # Wait for it to die gracefully
            except Exception:
                pass  # hope for the best
        if self.temp_file and os.path.exists(self.temp_file):
            os.unlink(self.temp_file)
        self.temp_file = None
        self.process = None
        self.partial_line = ""
        self.return_code = return_code

    def __del__(self):
        """Ensure the subprocess is terminated when the object is destroyed."""
        self.stop()
