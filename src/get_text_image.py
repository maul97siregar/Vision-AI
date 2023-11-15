"""
For extracting text from image

Function list:
- allowed_file
- get_text_from_image

Class list:
- GetTextFromImage
"""

import numpy as np

from datetime import datetime
from flask_restful import Resource
from flask import request, jsonify, send_file

from NawaAI.OCR import ocr
from src.utilization import cleanup

# list of allowed file extension
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png"}


def allowed_file(filename):
    """
    Check if the input file is in allowed extension

    filename: string

    return: True or False
    """

    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def get_text_from_image(file):
    """
    Get text from image using Google Vision AI
    then save the text to .txt file

    file: file_path or bytes

    return: output .txt file path
    """

    if file.filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS:
        text_line = ocr.GetTextFromImage(img=file.read())
        text_one_line = " ".join(text_line)
        text_one_line = [text_one_line]

    file_path = f'{file.filename.rsplit(".", 1)[0].lower()}_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.txt'
    np.savetxt(file_path, text_one_line, fmt="%s", encoding="utf-8")

    return file_path


class GetTextFromImage(Resource):
    """
    Extract Text From Image

    - get: show API name
    - post: for getting text from image
    """

    def get(self):
        msg = "Get Text From Image"
        return msg, 200

    def post(self):
        """
        For getting text from image

        params:
        - image

        return:
        - text from image
        """

        # get input file
        file = request.files["image"]

        # validate input file
        if file.filename == "":
            res = {"error": "Empyt Filename"}
            return jsonify(res)

        if not allowed_file(file.filename):
            res = {"error": f"Wrong File Extension, shoud be: {ALLOWED_EXTENSIONS}"}
            return jsonify(res)

        file_path = get_text_from_image(file)

        return_data = cleanup(file_path)

        # create response
        response = send_file(
            return_data,
            mimetype="text/plain",
            download_name=f"{file.filename.rsplit('.', 1)[1].lower()}.txt",
            as_attachment=True,
        )

        return response
