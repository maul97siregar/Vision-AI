from PIL import Image
import pytesseract
import os
from flask import Flask
from flask import request
from flask_restful import Resource, Api, reqparse
from datetime import datetime
import werkzeug
import json
from NawaAI.OCR import ocr_for_scanocr_web

class MapTemplateManual(Resource):
    def __init__(self):
        self.parse = reqparse.RequestParser()

    def post(self):

        # 1. Parsing FormData :
        self.parse.add_argument('imageFormFile', type=werkzeug.datastructures.FileStorage, location='files', required=True)
        self.parse.add_argument('detail_coordinates', location="form")
        args = self.parse.parse_args()
        imageFormFile = args["imageFormFile"]
        detail_coordinates = args["detail_coordinates"]
        # End Parsing FormData :

        # 2. Save Image :
        if not os.path.isdir("Image"):
            os.mkdir("Image")
        image_file = Image.open(imageFormFile)
        image_file.save('Image' + '/' + imageFormFile.filename)
        # End Save Image

        # 3. Split the content of detail_coordinates by four underscores (____) to get the 4-points coordinates of interest (
        # like transaction date, customer ID, etc ). Split each coordinates into x1, y1, x2, y2 values, crop the image following those four coordinates, 
        # then extract the text inside the cropped image, append them to the 'listOfOCRResults' List.
        listOfOCRResults = []
        stringOfCoordinateSets = detail_coordinates.split("____")
        
        for stringOfCoordinates in stringOfCoordinateSets :
            arrayOfCoordinates = stringOfCoordinates.split("|")
            croppedImageFormFile = image_file.crop(( float(arrayOfCoordinates[0]) , float(arrayOfCoordinates[1]), float(arrayOfCoordinates[2]), float(arrayOfCoordinates[3] )))
            croppedImageFormFile.save('Image' + '/cropped_' + imageFormFile.filename)

            images = [Image.open(x) for x in ['Image/TEST.jpeg', 'Image/TEST.jpeg', 'Image' + '/cropped_' + imageFormFile.filename, 'Image/TEST.jpeg', 'Image/TEST.jpeg']]
            widths, heights = zip(*(i.size for i in images))
            total_width = sum(widths)
            max_height = max(heights)
            new_im = Image.new('RGB', (total_width, max_height))
            x_offset = 0
            for im in images:
              new_im.paste(im, (x_offset,0))
              x_offset += im.size[0]
            new_im.save('Image' + '/cropped_combined_' + imageFormFile.filename)

            # ocr.GetTextFromImage is the function to extract text from the image.
            text_line = ocr_for_scanocr_web.GetTextFromImage('Image' + '/cropped_combined_' + imageFormFile.filename)

            # Processing the extracted text.
            temp_text_line = []
            for item in text_line:
                temp_text_line.append(item.replace("TEST","").strip())
            text_line = temp_text_line
            if 'TEST TEST' in text_line :
                testIndex = text_line.index('TEST TEST')
                del text_line[testIndex]
            if 'TESTTEST' in text_line :
                testIndex = text_line.index('TESTTEST')
                del text_line[testIndex]
            if '' in text_line :
                testIndex = text_line.index('')
                del text_line[testIndex]

            # Inserting the processed text to listOfOCRResults.
            if len(text_line) == 0 :
                listOfOCRResults.append(" ")
            else :
                listOfOCRResults.append(text_line[0])

            # Delete the image files after text extraction.
            os.remove('Image' + '/cropped_' + imageFormFile.filename)
            os.remove('Image' + '/cropped_combined_' + imageFormFile.filename)

        listOfOCRResults_InString = ""

        for OCRResult in listOfOCRResults :
            if OCRResult == "" or OCRResult == "_" or OCRResult == "__" or OCRResult is None:
                listOfOCRResults_InString += (" " + "____")
            else :
                listOfOCRResults_InString += (OCRResult + "____")
        listOfOCRResults_InString = listOfOCRResults_InString[:-4]

        # 4. Delete the original, full-size image.
        os.remove('Image' + '/' + imageFormFile.filename)

        # 5. Give it back as response.
        response = {
            'code': 200,
            'message': listOfOCRResults_InString
        }
        return response, 200
        # End Dump the result into JSON string, then give it back as response.

APPVersion = "1.0.0"
app = Flask(__name__)
api = Api(app)
api.add_resource(MapTemplateManual, '/GetOCRResults_Template_Manual')

if __name__ == "__main__":
    from waitress import serve
    serve(app, host="localhost", port=80)
