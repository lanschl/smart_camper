import os
import glob
import logging
import time
from typing import Optional

def setup_logging(log_dir: str, log_name_prefix: str, max_files: int = 5) -> str:
    """
    Sets up logging to a new file with a timestamp in the filename.
    Maintains only the `max_files` most recent log files.
    
    Returns the path to the newly created log file.
    """
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Cleanup old logs
    # We look for files matching the prefix and ending in .log
    log_pattern = os.path.join(log_dir, f"{log_name_prefix}_*.log")
    existing_logs = sorted(glob.glob(log_pattern))
    
    # If we have more than max_files - 1 (since we are about to create one), delete the oldest
    while len(existing_logs) >= max_files:
        oldest_log = existing_logs.pop(0)
        try:
            os.remove(oldest_log)
            print(f"Deleted old log file: {oldest_log}")
            # Also try to delete rotated files if any (e.g. .log.1)
            for rotated in glob.glob(f"{oldest_log}.*"):
                try:
                    os.remove(rotated)
                except OSError:
                    pass
        except OSError as e:
            print(f"Error deleting old log file {oldest_log}: {e}")

    # Create new log file path
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_filename = f"{log_name_prefix}_{timestamp}.log"
    log_path = os.path.join(log_dir, log_filename)

    return log_path
