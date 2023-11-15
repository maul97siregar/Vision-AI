"""
VisionAI OCR
- Get Response
- Get Response From File
- Get Text From Image
"""

import os
import io
import time
import uuid
import numpy as np
import logging
import matplotlib.pyplot as plt

from . import utils

from logging import FileHandler
from vlogging import VisualRecord
from shapely.geometry import Polygon
from PIL import Image, ImageDraw
from google.cloud import vision

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "config/key.json"


def GetResponse(content: bytes):
    """
    Process document from bytes to get json response from VisionAI

    content: img bytes

    returns:
        response: json response from VisionAI
    """

    client = vision.ImageAnnotatorClient()

    image = vision.Image(content=content)

    response = client.document_text_detection(image=image)

    if response.error.message:
        raise Exception(
            "{}\nFor more info on error messages, check: "
            "https://cloud.google.com/apis/design/errors".format(response.error.message)
        )

    return response


def GetResponseFromFile(in_file: str):
    """
    Process document from image to get json response from VisionAI

    in_file: image file path

    returns:
        response: json response from VisionAI
    """

    with io.open(in_file, "rb") as image_file:
        content = image_file.read()

    response = GetResponse(content)

    return response


def GetTextFromImage(img, sensitivity=0.5, display="off", savefig=False, debug=False):
    """
    Get text from image with VisionAI OCR

    img: bytes or image file path
    sensitivity: line detection sensitivity, lower means more sensitive, default 0.5
    display: show result, value = 'off', 'popup', 'notebook'
    savefig: save figure of text detection, text line detection, ocr result, default false
    debug: for debugging, default false

    returns:
        list of text line

    """

    if debug:
        format2 = "%(message)s <br/> <br/>"
        dt = time.strftime("%d-%b-%Y_%H-%M-%S")
        fn = f"debug_ocr_{dt}.html"
        logger = logging.getLogger()
        logger.setLevel(logging.DEBUG)
        fh = FileHandler(fn, mode="w")
        formatter2 = logging.Formatter(format2)
        fh.setFormatter(formatter2)
        logger.addHandler(fh)

        logging.debug(f"OCR: Debug mode enabled, saved in {fn}")

    # get response from input
    start_time_response = time.time()

    if isinstance(img, (bytes, bytearray)):
        response = GetResponse(img)
        image = Image.open(io.BytesIO(img))
    elif isinstance(img, str):
        img_path = img
        response = GetResponseFromFile(img_path)
        image = Image.open(img_path)
    else:
        print("not valid input")

    logging.debug(VisualRecord("Input Image", image, fmt="png"))

    original_image = image.copy()

    # correcting orientation
    orientations = utils.get_orientation(response)
    orientation = np.median(orientations)

    logging.debug(f"image orientation: {orientation}")

    if orientation == 90:
        image = image.rotate(90, expand=True)
        original_image = image.copy()
        image_bytes = utils.img_to_bytes(image)
        response = GetResponse(image_bytes)

    elif orientation == 180:
        image = image.rotate(180, expand=True)
        original_image = image.copy()
        image_bytes = utils.img_to_bytes(image)
        response = GetResponse(image_bytes)

    elif orientation == 270:
        image = image.rotate(270, expand=True)
        original_image = image.copy()
        image_bytes = utils.img_to_bytes(image)
        response = GetResponse(image_bytes)

    finish_time_response = time.time() - start_time_response

    logging.debug(f"get response time: {finish_time_response}")

    start_time_text = time.time()

    # for storing text with polygon and id
    text_w_poly = []
    # for storing text with point and id
    text_w_point = []
    id = 0
    for text in response.text_annotations[1:]:
        points = []
        for point in text.bounding_poly.vertices:
            points.append((point.x, point.y))
        text_w_poly.append([points, text.description, id])
        text_w_point.append([points[0], text.description, id])
        id += 1

    # sort the text by x axis
    text_w_poly = sorted(text_w_poly, key=lambda x: x[0][0][0])

    # GET TEXT
    # check if text1 is in the range of text2 and vice versa
    # if True then line merge

    loop_line = True
    listed_text_id = []
    idx1 = 0
    idx2 = 0
    # final_text = []
    final_text_full = []
    c = image.size[0]

    while loop_line:
        loop_current = True
        # text_line = []
        text_line_full = []
        temp = text_w_poly[idx1]
        idx1 += 1

        if temp[2] in listed_text_id:
            loop_current = False

        while loop_current:
            idx2 = 0
            overlap = 0
            loop_next = True
            current_text = temp

            # text_line.append(current_text[1])
            text_line_full.append(current_text)

            while loop_next:
                next_text = text_w_poly[idx2]

                id1 = current_text[2]
                id2 = next_text[2]

                x1 = current_text[0][1][0]
                x2 = next_text[0][1][0]

                if id1 != id2 and x2 > x1 and next_text[2] not in listed_text_id:
                    in_sect_left = utils.check_left(current_text[0], next_text[0], c)
                    in_sect_right = utils.check_right(current_text[0], next_text[0], c)

                    # uncomment to test
                    # if current_text[1] == 'Operator' and next_text[1] == ':':
                    #     print(f'>> {current_text[1], next_text[1], in_sect_left, in_sect_right}')

                    if in_sect_left > sensitivity and in_sect_right > sensitivity:
                        overlap += 1
                        temp = next_text
                        loop_next = False
                        listed_text_id.append(current_text[2])
                        listed_text_id.append(next_text[2])

                        # uncomment to test
                        # if current_text[1] == ':' : #and next_text[1] == ':':
                        #     print(f'>> {current_text[1], next_text[1], in_sect_left, in_sect_right}')

                if idx2 == (len(text_w_poly) - 1):
                    loop_next = False

                idx2 += 1

            if overlap == 0:
                loop_current = False
                # final_text.append(' '.join(text_line))
                final_text_full.append(text_line_full)

        if idx1 == (len(text_w_poly) - 1):
            loop_line = False

    # sort by y axis
    final_text_full = sorted(final_text_full, key=lambda x: x[0][0][0][1])

    final_text_per_line = []
    for tl in final_text_full:
        text_line = []
        for t in tl:
            text_line.append(t[1])
        final_text_per_line.append(" ".join(text_line))

    finish_time_text = time.time() - start_time_text

    # show ocr result
    if display == "popup" or display == "notebook" or debug:
        # draw text boundingbox
        draw_text_box = ImageDraw.Draw(original_image)
        for poly in text_w_poly:
            draw_text_box.polygon(poly[0], outline=(0, 255, 0), width=3)

        logging.debug(VisualRecord("Detected Text", original_image, fmt="png"))

        # draw line text
        polygons_up = []
        polygons_down = []
        polygons = []

        for line_full in final_text_full:
            poly_upper = []
            poly_bottom = []

            for poly in line_full:
                for id, p in enumerate(poly[0]):
                    if id == 0 or id == 1:
                        poly_upper.append(p)
                    elif id == 3:
                        poly_bottom.append(p)
                    else:
                        poly_bottom.append(p)

            poly_bottom = sorted(poly_bottom, key=lambda x: x[0])

            polygons_up.append(poly_upper)
            polygons_down.append(poly_bottom)
            polygons.append(poly_upper + poly_bottom[::-1])

        draw_line_box = ImageDraw.Draw(image)

        for poly in polygons:
            poly = Polygon(poly).buffer(2.0)
            draw_line_box.polygon(poly.exterior.coords, outline=(0, 0, 255), width=3)

        logging.debug(VisualRecord("Detected Text Line", image, fmt="png"))

        if display == "popup":
            image.show()

        if display == "notebook":
            if isinstance(img, str):
                title = img
            plot_text = (
                "\n".join(final_text_per_line)
                + f"\n\nresponse: {str(finish_time_response)[:5]}\nget_text: {str(finish_time_text)[:5]}\nsensitivity: {str(sensitivity)}"
            )
            plt.figure(figsize=(30, 15))
            plt.subplot(131)
            plt.title(title)
            plt.imshow(original_image)
            plt.axis("off")
            plt.subplot(132)
            plt.imshow(image)
            plt.axis("off")
            plt.subplot(133)
            plt.text(0.5, 0.5, plot_text, ha="center", va="center", wrap=True)
            plt.axis("off")
            if savefig:
                save_folder = f"output_fig_ocr"
                os.makedirs(save_folder, exist_ok=True)
                save_path = os.path.join(save_folder, str(uuid.uuid4()) + ".jpg")
                plt.savefig(save_path)
            plt.show()

    logging.debug(f"OCR RESULT: {final_text_per_line}")
    image.close()
    return final_text_per_line
