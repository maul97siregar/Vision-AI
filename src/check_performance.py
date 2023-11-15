"""
Check Performance Module

Function list:
- check_resource
"""

import psutil


def check_resource(text=""):
    """
    for checking cpu and memory usage

    text: text to show
    """

    process = psutil.Process()
    memory_info = process.memory_info()

    print(f"==> performance: {text} <==")
    print(
        f"CPU: {psutil.cpu_count(), psutil.cpu_count(logical=False)} - {process.cpu_percent(interval=1)} %"
    )
    print(
        f"Pemakaian Memori: {memory_info.rss / (1024 * 1024):.2f} MB - {process.memory_percent()}"
    )
    print("=====" * 5)
