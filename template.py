import pytesseract
import cv2
import json
import os
import werkzeug
import requests

from numpy import float32, zeros_like
from flask_restful import Resource, reqparse
from PIL import Image, ImageDraw

gateway_url = os.environ.get("GATEWAY_URL", 'http://34.111.194.136/gateway/')

def getData(id):
    dataResponse = requests.get(
        gateway_url + 'api/templateocr/get?templateid=' + str(id)).text
    responseGateway = json.loads(dataResponse)

    responseGateway['detail']

    return responseGateway


def templateResult(filename, tempId):

    response = requests.get(
        '%sapi/templateocr/get?templateid=%d' % (gateway_url, tempId)).text
    responseGateway = json.loads(response)

    responseGateway['detail']

    detailList = []
    formInterest = []

    for r in responseGateway['detail']:
        detailList.append([r['pk_templatedetail_id'],
                           r['fk_templateocr_id'],
                           r['fieldname'],
                           r['x1'],
                           r['y1'],
                           r['x2'],
                           r['y2']])

        x1, y1, x2, y2, field = int(r['x1']), int(r['y1']), int(
            r['x2']), int(r['y2']), str(r['fieldname'])

        formInterest.append([(x1, y1), (x2, y2), field])

    per = 25

    # harap disesuaikan dengan directory installer Pytesseract di laptop anda
    # pytesseract.pytesseract.tesseract_cmd = 'C:\\Program Files\\Tesseract-OCR\\tesseract.exe'
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    imgQ = cv2.imread('Image' + '/' + filename)
    heigh, weight, c = imgQ.shape
    orb = cv2.ORB_create(5000)
    keyPoints, desc = orb.detectAndCompute(imgQ, None)

    path = 'Image'
    # myPicList = os.listdir(path)

    # for j, y in enumerate(myPicList):

    img = cv2.imread(path + "/" + filename)
    keyPoints2, desc2 = orb.detectAndCompute(img, None)
    bruteForce = cv2.BFMatcher(cv2.NORM_HAMMING)

    matches = bruteForce.match(desc2, desc)
    matches = sorted(matches, key=lambda x: x.distance)

    matchResult = matches[:int(len(matches)*(per/100))]
    imgMatch = cv2.drawMatches(
        img, keyPoints2, imgQ, keyPoints, matchResult[:100], None, flags=2)

    srcPoints = float32(
        [keyPoints2[m.queryIdx].pt for m in matchResult]).reshape(-1, 1, 2)

    dstPoints = float32(
        [keyPoints[m.trainIdx].pt for m in matchResult]).reshape(-1, 1, 2)

    M, _ = cv2.findHomography(srcPoints, dstPoints, cv2.RANSAC, 5.0)
    imgScan = cv2.warpPerspective(img, M, (weight, heigh))

    imgShow = imgScan.copy()
    imgMask = zeros_like(imgShow)

    dataResult = {}

    for x, r in enumerate(formInterest):
        # cv2.rectangle(imgMask, (r[0][0], r[0][1]),
        #               (r[1][0], r[1][1]), (0, 255, 0), cv2.FILLED)
        # imgShow = cv2.addWeighted(imgShow, 0.99, imgMask, 0.1, 0)

        imgCrop = imgScan[r[0][1]:r[1][1], r[0][0]:r[1][0]]
        if imgCrop.any():
            field = pytesseract.image_to_string(imgCrop).replace('\f', '')
        else:
            field = ''
        # formInterest[x] = r[2].replace("\n", "")

        key = r[2]
        dataResult[key] = field.replace('\n', '')

    # response = {
    #     'code': 200,
    #     'status': "OK",
    #     'file_name': filename,
    #     'message': 'Success',
    #     'pk_templatedetail_id': tempId,
    #     'data': dataResult
    # }

    return dataResult


class MapTemplate(Resource):
    def __init__(self):
        self.parse = reqparse.RequestParser()

    def get(self):
        self.parse.add_argument(
            'templateId', location="args",  type=int)
        args = self.parse.parse_args()

        tempId = args["templateId"] or 1

        ok = "Data Detail Template Berhasil Diambil"
        print(gateway_url)

        data = getData(tempId)
        response = {
            'code': 200,
            'message': ok,
            'data': data
        }

        return response, 200

    def post(self):
        self.parse.add_argument(
            'image', type=werkzeug.datastructures.FileStorage, location='files', required=True)

        self.parse.add_argument(
            'templateId', location="form",  type=int)

        args = self.parse.parse_args()

        image = args["image"]
        tempId = args["templateId"]

        if not os.path.isdir("Image"):
            os.mkdir("Image")

        image_file = Image.open(image)
        image_file.save('Image' + '/' + image.filename)

        result = templateResult(image.filename, tempId)

        return result, 200

