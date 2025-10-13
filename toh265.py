#!/usr/bin/env python3
import os
import sys
import subprocess
import shlex
import re
import time
import glob
from datetime import timedelta
import ffmpeg

# --- Conversion Criteria Constants (Customize these) ---
TARGET_WIDTH = 1920
TARGET_HEIGHT = 1080
TARGET_CODECS = ['h265', 'hevc']
MAX_BITRATE_KBPS = 2800 # about 20MB/min (or 800MB for 40m)

# --- End Criteria Constants ---


# --- Configuration ---
OUTPUT_CRF = 24          # Target CRF for new x265 encodes
PROGRESS_UPDATE_INTERVAL = 3  # Seconds between print updates

# Regex to find FFmpeg progress lines (from stderr)
# Looks for 'frame=  XXXXX' and 'time=00:00:00.00' and 'speed=XX.XXx'
PROGRESS_RE = re.compile(
    r"frame=\s*(\d+)\s+.*time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})\s+.*speed=\s*(\d+\.\d+)x"
)

# Regex to find the video stream's duration from ffprobe
DURATION_RE = re.compile(r'"duration":\s*"(\d+\.\d+)"')

# ==============================================================================
# UTILITY FUNCTIONS
# ==============================================================================

def get_video_duration(file_path):
    """Uses ffprobe to get the total duration of the video stream in seconds."""
    cmd = shlex.split(f'ffprobe -v error -select_streams v:0 -show_entries format=duration -of json "{file_path}"')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        match = DURATION_RE.search(result.stdout)
        if match:
            return float(match.group(1))
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        print(f"Error getting duration for {file_path} with ffprobe: {e}")
    return 0.0
import subprocess
import json
import os

def get_video_metadata(file_path):
    """
    Extracts video metadata using ffprobe and returns it as a Python dictionary.

    Args:
        file_path (str): The path to the video file.

    Returns:
        dict or None: A dictionary containing the ffprobe output, or None if an
                      error occurs (e.g., file not found, ffprobe fails).
    """
    # Check if the file exists
    if not os.path.exists(file_path):
        print(f"Error: File not found at '{file_path}'")
        return None

    # ffprobe command to output format and stream information in JSON format
    # -v error: Suppress all non-error messages (like the banner)
    # -print_format json: Output in JSON format
    # -show_format: Include container format information
    # -show_streams: Include stream (video, audio, etc.) information
    command = [
        'ffprobe',
        '-v', 'error',
        '-print_format', 'json',
        '-show_format',
        '-show_streams',
        file_path
    ]

    try:
        # Execute the command
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True  # Raise a CalledProcessError for non-zero exit codes
        )

        # Parse the JSON output
        ### print(result.stdout)
        metadata = json.loads(result.stdout)
        return metadata

    except FileNotFoundError:
        # This occurs if 'ffprobe' is not found in the system's PATH
        print("Error: ffprobe command not found. Ensure FFmpeg/ffprobe is installed and in your system PATH.")
        return None
    except subprocess.CalledProcessError as e:
        # This occurs if ffprobe runs but returns an error code (e.g., file is corrupt)
        print(f"Error running ffprobe for '{file_path}':")
        print(f"  Command: {' '.join(e.cmd)}")
        print(f"  Return Code: {e.returncode}")
        print(f"  Stderr: {e.stderr.strip()}")
        return None
    except json.JSONDecodeError:
        # This occurs if the output is not valid JSON
        print(f"Error: Failed to decode JSON from ffprobe output for '{file_path}'.")
        # print(f"Raw output: {result.stdout.strip()}") # Uncomment for debugging
        return None
    except Exception as e:
        # Catch any other unexpected errors
        print(f"An unexpected error occurred: {e}")
        return None

def already_converted(filepath):
    """
    Checks if a video file already meets the updated conversion criteria:
    1. Resolution is at least TARGET_WIDTH x TARGET_HEIGHT.
    2. Video codec is TARGET_CODECS (e.g., 'h264').
    3. Video bitrate is below MAX_BITRATE_KBPS.

    Args:
        filepath (str): The path to the video file.

    Returns:
        bool: True if the file meets all criteria, False otherwise.
    """
    metadata = get_video_metadata(filepath)

    if metadata is None:
        print(f"Could not retrieve valid video metadata for {os.path.basename(filepath)}. Will convert.")
        return False

    # Extract values for comparison
    video_stream = next((s for s in metadata.get('streams', [])
                         if s.get('codec_type') == 'video'), None)
    width = int(video_stream.get('width', 0))
    height = int(video_stream.get('height', 0))
    codec = video_stream.get('codec_name', 'unk_codec')
    bitrate = int(int(metadata["format"].get('bit_rate', 0))/1000) # in KBPS

    # 1. Check Resolution
    # Assuming resolution check is 'at least' the target
    res_ok = (width is not None and width >= TARGET_WIDTH) and \
             (height is not None and height >= TARGET_HEIGHT)

    # 2. Check Codec
    codec_ok = (codec is not None and codec.lower() in TARGET_CODECS)

    # 3. Check Bitrate (with tolerance)
    bitrate_ok = bool(bitrate <= MAX_BITRATE_KBPS)

    if res_ok and codec_ok and bitrate_ok:
        print(f"... already meets conversion criteria:\n"
              f"  Res: {width}x{height} ({res_ok}), Codec: {codec} ({codec_ok}),\n"
              f"  Bitrate: {bitrate:.2f} kbps ({bitrate_ok})")
        return True
    else:
        print(f"... needs conversion.\n"
              f"  (Res: {width}x{height} - Target >= {TARGET_WIDTH}x{TARGET_HEIGHT},\n"
              f"  Codec: {codec} - Target '{TARGET_CODECS}',\n"
              f"  Bitrate: {bitrate} kbps - Target: <= {MAX_BITRATE_KBPS}")
        return False


def monitor_transcode_progress(input_file, temp_file, duration_seconds):
    """
    Runs the FFmpeg transcode command and monitors its output for a non-scrolling display.
    """
    # Define the FFmpeg command
    ffmpeg_cmd = [
        'ffmpeg',
        '-y',                           # Overwrite temp file if exists
        '-i', input_file,
        '-c:v', 'libx265',
        '-crf', str(OUTPUT_CRF),
        '-preset', 'medium',
        '-c:a', 'copy',
        '-c:s', 'copy',
        '-map', '0',
        temp_file
    ]

    # Start FFmpeg subprocess
    # We pipe stderr to capture progress updates
    process = subprocess.Popen(
        ffmpeg_cmd,
        stdout=subprocess.DEVNULL,  # Discard normal stdout output
        stderr=subprocess.PIPE,     # Capture progress messages from stderr
        text=True,                  # Read output as text (string)
        bufsize=1
    )

    start_time = time.time()
    last_update_time = start_time
    total_duration_formatted = str(timedelta(seconds=int(duration_seconds)))

    # --- Progress Monitoring Loop ---
    # Read stderr line-by-line until the process finishes
    for line in process.stderr:
        match = PROGRESS_RE.search(line)

        # Check if the line contains progress data and if the update interval has passed
        if match and (time.time() - last_update_time) >= PROGRESS_UPDATE_INTERVAL:

            # 1. Extract values from the regex match
            try:
                groups = match.groups()

                # The first two parts (H and M) are integers. The third part (S.ms) is the float.
                h = int(groups[1])
                m = int(groups[2])
                s = int(groups[3])
                ms = int(groups[4])
                time_encoded_seconds = h * 3600 + m * 60 + s + ms / 100
                speed = float(match.group(6))
            except Exception:
                print(f"\n{line=} {groups=}")
                raise

            elapsed_time_sec = int(time.time() - start_time)

            # 2. Calculate remaining time
            if duration_seconds > 0:
                percent_complete = (time_encoded_seconds / duration_seconds) * 100

                if percent_complete > 0 and speed > 0:
                    # Time Remaining calculation (rough estimate)
                    # Remaining Time = (Total Time - Encoded Time) / Speed
                    remaining_seconds = (duration_seconds - time_encoded_seconds) / speed
                    remaining_time_formatted = str(timedelta(seconds=int(remaining_seconds)))
                else:
                    remaining_time_formatted = "N/A"
            else:
                percent_complete = 0.0
                remaining_time_formatted = "N/A"

            # 3. Format the output line
            # \r at the start makes the console cursor go back to the beginning of the line
            progress_line = (
                f"\r{timedelta(seconds=elapsed_time_sec)} | "
                f"[{percent_complete:5.1f}%] | "
                f"Time {str(timedelta(seconds=int(time_encoded_seconds))) or '??'}/{total_duration_formatted} | "
                f"ETA {remaining_time_formatted} | "
                f"Speed {speed:.1f}x"
            )

            # 4. Print and reset timer
            print(progress_line, end='', flush=True)
            last_update_time = time.time()

    # Wait for the process to truly finish and get the return code
    process.wait()

    # Clear the progress line and print final status
    print('\r' + ' ' * 120, end='', flush=True) # Overwrite last line with spaces

    if process.returncode == 0:
        print(f"\r{input_file}: Transcoding FINISHED (Elapsed: {timedelta(seconds=int(time.time() - start_time))})")
        return True # Success
    else:
        # Print a final error message
        print(f"\r{input_file}: Transcoding FAILED (Return Code: {process.returncode})")
        # In a real script, you'd save or display the full error output from stderr here.
        return False

# A common list of video extensions ffmpeg can typically handle.
# NOTE: The check is *case-insensitive* by converting to lowercase.
VIDEO_EXTENSIONS = {
    '.mp4', '.mov', '.mkv', '.avi', '.webm', '.flv', 
    '.wmv', '.mpg', '.mpeg', '.3gp', '.m4v', '.ts',
    '.ogg', '.ogv'
    # You may need to add or remove extensions based on your specific requirements
}
# Prefixes to skip (case-sensitive as requested)
SKIP_PREFIXES = ('TEMP.', 'ORIG.')

def is_valid_video_file(filename):
    """
    Checks if a file meets all the criteria:
    1. Does not start with 'TEMP.' or 'ORIG.'.
    2. Has a common video file extension (case-insensitive).
    """
    
    # 1. Check for prefixes to skip
    if filename.startswith(SKIP_PREFIXES):
        print(f"Skipping '{filename}': Starts with a forbidden prefix.")
        return False

    # Get the file extension and convert to lowercase for case-insensitive check
    # os.path.splitext returns a tuple: (root, ext)
    _, ext = os.path.splitext(filename)
    
    # 2. Check if the extension is a recognized video format
    if ext.lower() not in VIDEO_EXTENSIONS:
        print(f"Skipping '{filename}': Not a recognized video file extension ('{ext.lower()}').")
        return False
        
    # The file meets all criteria
    return True


if __name__ == '__main__':
    # sys.argv is the list of command-line arguments. sys.argv[0] is the script name.
    files_to_process = sys.argv[1:]

    if not files_to_process:
        print("Usage: python your_script.py <file1> <file2> ...")
        sys.exit(1)

    print(f"Checking {len(files_to_process)} files...")
    
    # --- The main loop change is here ---
    for input_file in files_to_process:
        if not is_valid_video_file(input_file):
            continue  # Skip to the next file in the loop
 
        print("\n" + "=" * 80)
        print(f"{input_file}")

        # 1. Quality Check
        if already_converted(input_file):
            continue

        # --- File names for the safe replacement process ---
        temp_file = f"TEMP.{input_file}"
        orig_backup_file = f"ORIG.{input_file}"

        # 2. Get total video duration for ETA calculation
        duration = get_video_duration(input_file)
        if duration == 0.0:
            print(f"WARNING: Could not determine video duration. Progress monitor will only show elapsed time.")

        # 3. Transcode with monitored progress
        success = monitor_transcode_progress(input_file, temp_file, duration)

        # 4. Atomic Swap (Safe Replacement)
        if success:
            try:
                # Rename original to backup
                os.rename(input_file, orig_backup_file)
                print(f"Original moved to {orig_backup_file}.")

                # Rename temporary file to the original filename
                os.rename(temp_file, input_file)
                print(f"SUCCESS: New H.265 file is now {input_file}.")

            except OSError as e:
                print(f"CRITICAL ERROR during file swap for {input_file}: {e}")
                print(f"Original: {orig_backup_file}, New: {temp_file}. Manual cleanup required.")
        else:
            # Transcoding failed, delete the temporary file
            if os.path.exists(temp_file):
                os.remove(temp_file)
                print(f"FFmpeg failed. Deleted incomplete {temp_file}.")

if __name__ == "__main__":
    main()
