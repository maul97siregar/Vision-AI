"""
provide utilization for OCR
"""

import io
import math
import numpy as np
from shapely.geometry import Polygon


def new_point_extend_right(x1, x2, y1, y2, c):
    """
    extending line to the right

    x1,x2,y1,y2
    c: extend length

    returns:
        new x,y
    """

    c = c * -1
    d = math.sqrt(((x1 - x2) ** 2) + ((y1 - y2) ** 2))
    d1 = d - c
    x = ((x1 * d1) + (x2 * c)) / (c + d1)
    y = ((y1 * d1) + (y2 * c)) / (c + d1)

    return (x, y)


def new_point_extend_left(x1, x2, y1, y2, c):
    """
    extending line to the left

    x1, x2, y1, y2
    c: extend length

    returns:
        new x,y
    """

    c = c * -1
    d = math.sqrt(((x1 - x2) ** 2) + ((y1 - y2) ** 2))
    d1 = d - c
    x = ((x1 * c) + (x2 * d1)) / (c + d1)
    y = ((y1 * c) + (y2 * d1)) / (c + d1)

    return (x, y)


def check_right(poly1, poly2, c):
    """
    check overlap to the right

    poly1: polygon left side
    poly2: polygon right side
    c: extend length polygon

    returns:
        overlap percentage
    """

    right_top_corner = new_point_extend_right(
        poly1[1][0], poly1[0][0], poly1[1][1], poly1[0][1], c
    )
    right_bottom_corner = new_point_extend_right(
        poly1[2][0], poly1[3][0], poly1[2][1], poly1[3][1], c
    )

    poly1 = [poly1[0], right_top_corner, right_bottom_corner, poly1[3]]
    poly1_new = Polygon(poly1)

    if not poly1_new.is_valid:
        # display(poly1_new)
        poly1 = [poly1[0], right_bottom_corner, right_top_corner, poly1[3]]
        poly1_new = Polygon(poly1)

    poly2 = Polygon(poly2)

    if poly1_new.intersects(poly2):
        overlap = poly1_new.intersection(poly2).area / poly2.area
        return overlap
    else:
        return 0


def check_left(poly1, poly2, c):
    """
    check overlap to the left

    poly1: polygon left side
    poly2: polygon right side
    c: extend length polygon

    returns:
        overlap percentage
    """

    left_top_corner = new_point_extend_left(
        poly2[1][0], poly2[0][0], poly2[1][1], poly2[0][1], c
    )
    left_bottom_corner = new_point_extend_left(
        poly2[2][0], poly2[3][0], poly2[2][1], poly2[3][1], c
    )

    poly2 = [left_top_corner, poly2[0], poly2[3], left_bottom_corner]
    poly2_new = Polygon(poly2)

    if not poly2_new.is_valid:
        # display(poly1_new)
        poly2 = [left_top_corner, poly2[0], left_bottom_corner, poly2[3]]
        poly2_new = Polygon(poly2)

    poly1 = Polygon(poly1)

    if poly2_new.intersects(poly1):
        overlap = poly2_new.intersection(poly1).area / poly1.area
        return overlap
    else:
        return 0


def get_orientation(response):
    """
    get orientation of text image

    response: VisionAI response

    returns:
        orientation angle
    """

    MIN_WORD_LENGTH_FOR_ROTATION_INFERENCE = 4

    orientations = []

    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    if len(word.symbols) < MIN_WORD_LENGTH_FOR_ROTATION_INFERENCE:
                        continue
                    first_char = word.symbols[0]
                    last_char = word.symbols[-1]
                    first_char_center = (
                        np.mean([v.x for v in first_char.bounding_box.vertices]),
                        np.mean([v.y for v in first_char.bounding_box.vertices]),
                    )
                    last_char_center = (
                        np.mean([v.x for v in last_char.bounding_box.vertices]),
                        np.mean([v.y for v in last_char.bounding_box.vertices]),
                    )

                    # upright or upside down
                    top_right = last_char.bounding_box.vertices[1]
                    bottom_right = last_char.bounding_box.vertices[2]
                    if np.abs(first_char_center[1] - last_char_center[1]) < np.abs(
                        top_right.y - bottom_right.y
                    ):
                        if first_char_center[0] <= last_char_center[0]:  # upright
                            orientations.append(0)
                            # print(0)
                        else:  # updside down
                            orientations.append(180)
                            # print(180)
                    else:  # sideways
                        if first_char_center[1] <= last_char_center[1]:
                            orientations.append(90)
                            # print(90)
                        else:
                            orientations.append(270)
                            # print(270)
    return orientations


def img_to_bytes(img):
    """
    convert PIL image variable to bytes

    img: PIL Image

    returns:
        image bytes
    """

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr
