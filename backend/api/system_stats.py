"""
YTAutomation — System Stats

Provides hardware usage monitoring (CPU, RAM, disk) via psutil.
"""

import os
import psutil
from pathlib import Path

from config import settings


def get_system_stats() -> dict:
    """
    Collect current system resource usage.

    Returns:
        Dict with cpu_percent, ram_percent, ram_used_gb, ram_total_gb,
        disk_percent, disk_used_gb, disk_total_gb.
    """
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.1)

    # Process Stats (The backend process running the pipeline)
    process = psutil.Process(os.getpid())
    process_cpu = process.cpu_percent(interval=0.1)
    
    # Process RAM (RSS) in GB
    process_memory_info = process.memory_info()
    process_ram_gb = round(process_memory_info.rss / (1024 ** 3), 2)

    # Global RAM
    mem = psutil.virtual_memory()
    ram_percent = mem.percent
    ram_used_gb = round(mem.used / (1024 ** 3), 1)
    ram_total_gb = round(mem.total / (1024 ** 3), 1)

    # Disk (check the volume where output_dir lives)
    try:
        output_path = str(settings.output_dir.absolute())
        disk = psutil.disk_usage(output_path)
        disk_percent = disk.percent
        disk_used_gb = round(disk.used / (1024 ** 3), 1)
        disk_total_gb = round(disk.total / (1024 ** 3), 1)
        disk_free_gb = round(disk.free / (1024 ** 3), 1)
    except Exception:
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent
        disk_used_gb = round(disk.used / (1024 ** 3), 1)
        disk_total_gb = round(disk.total / (1024 ** 3), 1)
        disk_free_gb = round(disk.free / (1024 ** 3), 1)

    return {
        "cpu_percent": cpu_percent,
        "cpu_count": psutil.cpu_count(),
        "process_cpu_percent": process_cpu,
        "process_ram_gb": process_ram_gb,
        "ram_percent": ram_percent,
        "ram_used_gb": ram_used_gb,
        "ram_total_gb": ram_total_gb,
        "disk_percent": disk_percent,
        "disk_used_gb": disk_used_gb,
        "disk_total_gb": disk_total_gb,
        "disk_free_gb": disk_free_gb,
    }
