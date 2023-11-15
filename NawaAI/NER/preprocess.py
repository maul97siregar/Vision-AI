"""
Apply preprocessing before prediction

List of preprocessing:
- Rotate image
- Get image angle
"""
import cv2
import numpy as np
import math


def rotate_image(img, angle):
    """
    Rotating image

    img = from cv2.imread()

    returns:
        rotated image
    """

    (h, w) = img.shape[:2]
    center_img = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center_img, angle, 1.0)
    rotated_image = cv2.warpAffine(
        img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )

    return rotated_image


def get_image_angle(img, angle_threshold=35):
    """
    To get image angle

    img: from cv2.imread()
    angle_threshold: threshold of angle that will be obtained, 35 is default and optimum value

    returns:
      angle_median: median value of angles
      angles: list of angle values
      lines_coordinate: list of (x1, y1), (x2, y2) line coordinate
    """

    lines = cv2.HoughLines(
        img,
        1,
        np.pi / 180,
        #    100, # default
        200,
        None,
        0,
        0,
    )

    # Loop over all detected lines

    img_line = img.copy()

    angles = []
    lines_coordinate = []
    if lines is not None:
        for line in lines:
            rho = line[0][0]
            theta = line[0][1]
            a = math.cos(theta)
            b = math.sin(theta)
            x0 = a * rho
            y0 = b * rho
            pt1 = (int(x0 + 1000 * (-b)), int(y0 + 1000 * (a)))
            pt2 = (int(x0 - 1000 * (-b)), int(y0 - 1000 * (a)))
            x1, y1 = pt1
            x2, y2 = pt2

            # Calculate the angle of the line
            angle = np.arctan2(y2 - y1, x2 - x1) * 180.0 / np.pi

            # If the angle is close to 0 degrees (horizontal), draw the line and print the angle
            if abs(angle) < angle_threshold:
                lines_coordinate.append([x1, y1, x2, y2])
                cv2.line(img_line, (x1, y1), (x2, y2), (0, 0, 255), 3, cv2.LINE_AA)
                angles.append(angle)

        # Get final angle from median
        angle_median = np.median(angles)

        import matplotlib.pyplot as plt

        plt.title(f"hough lines: {len(angles)}, {angle_median}")
        plt.imshow(cv2.cvtColor(img_line, cv2.COLOR_BGR2RGB))
        plt.show()

    # If no line found
    else:
        angle_median = 0

    return angle_median, angles, lines_coordinate
