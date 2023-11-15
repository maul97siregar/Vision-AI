"""
For utilization method

Function list:
- zip_folder
- delete_contents_of_folder
- is_valid_folder_name
- zip_contains_file
- cleanup
"""

import os
import re
import io
import shutil
import zipfile


def zip_folder(folder_path, output_path):
    """
    Compress a folder into a zip file.

    folder_path: The path of the folder to be compressed.
    output_path: The path of the resulting zip file.
    """
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname=arcname)


def delete_contents_of_folder(folder_path):
    """
    To delete the contents of a folder, including files and subfolders.

    folder_path: The path of the folder whose contents will be deleted.
    """
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        if os.path.isfile(item_path):
            os.unlink(item_path)  # deleting file
        elif os.path.isdir(item_path):
            shutil.rmtree(item_path)  # deleting subfolder and its inside


def is_valid_folder_name(folder_name):
    """
    For checking valid folder name

    folder_name: string
    """

    # Define a regular expression pattern for a valid folder name
    pattern = r"^[a-zA-Z0-9_-]+$"  # This pattern allows letters, numbers, underscores, and hyphens

    # Use re.match to check if the folder_name matches the pattern
    return re.match(pattern, folder_name) is not None


def zip_contains_file(zip_file_path, file_name):
    """
    For checking if file is inside a zip

    zip_file_path: zip path
    file_name: file to check

    return: True or False
    """

    with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
        return file_name in zip_ref.namelist()


def cleanup(file_path):
    """
    For cleaning file after process

    file_path: file path

    return: return_data file in bytes
    """

    # convert to bytes
    return_data = io.BytesIO()
    with open(file_path, "rb") as f:
        return_data.write(f.read())
    return_data.seek(0)

    # cleanup
    os.remove(file_path)

    return return_data
