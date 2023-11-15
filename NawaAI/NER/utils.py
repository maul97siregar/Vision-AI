"""
provide utilization modules:
- create_folder
- split_list_2
- split_list_3
"""
import os


def create_folder(path: str):
    """
    for creating folder that doesn't exist
    """

    if not os.path.exists(path):
        os.makedirs(path)


def split_list_2(lst, percentage):
    """
    split list to 2 section from percentage
    """
    # Calculate the index at which to split the list
    split_index = int(len(lst) * percentage / 100)

    # Split the list into two sections
    section1 = lst[:split_index]
    section2 = lst[split_index:]

    return section1, section2


def split_list_3(lst, percentage):
    """
    split list to 3 section from percentage
    """
    total = sum(percentage)
    if total != 100:
        raise ValueError("Total percentage must be 100.")

    n = len(lst)
    sizes = [int(n * pct / 100) for pct in percentage]
    if sum(sizes) < n:
        sizes[0] += n - sum(sizes)

    sections = []
    start = 0
    for size in sizes:
        end = start + size
        sections.append(lst[start:end])
        start = end

    return sections
