"""
main API

Receipt value extractor

run:
    python main.py
"""

import os
import time
from tqdm import tqdm

# Define the working directory
working_dir = os.getcwd()

# Create a list to store the directory and file names
directory_and_file_list = []

# Recursively scan the working directory
for root, dirs, files in tqdm(os.walk(working_dir)):
    for directory in dirs:
        directory_and_file_list.append(os.path.relpath(os.path.join(root, directory), working_dir))
    for file in files:
        directory_and_file_list.append(os.path.relpath(os.path.join(root, file), working_dir))

directory_and_file_list.append(f"working dir: {working_dir}")

# Define the output text file
output_file = "directory_and_file_list.txt"

# Write the results to the text file
with open(output_file, "w") as f:
    for item in directory_and_file_list:
        f.write(item + "\n")

print(f"Scanned {len(directory_and_file_list)} items and saved to {output_file}")

print(working_dir)
from flask import Flask
from flask_restful import Api

from src.check_performance import check_resource

# check_resource("start main.py")

os.environ['GRPC_DNS_RESOLVER'] = 'native'

print(f"info: preparing..")
start_time = time.time()

from vision import VisionNew
from visionold import Vision
from template import MapTemplate
from visionAll import VisionAll
from visionAPI import VisionAPI
from GetOCRResults_Template_Manual import MapTemplateManual

app = Flask(__name__)
api = Api(app)

# check_resource("create app, api")

from src.predict_bbm import BbmPrediction
from src.predict_pdam import PdamPrediction
from src.get_text_image import GetTextFromImage
from src.train_model import TrainNER
from src.levenshtein_utils import LevenshteinUtils
from src.model_utils import AddModel, ShowModel, ShowModelInfo, DeleteModel, SelectModel

# check_resource("loaded modules")

print(f"info: prepare done, load time: {time.time() - start_time} second")

api.add_resource(Vision, "/visionold")
# api.add_resource(VisionNew, '/vision')
api.add_resource(MapTemplate, "/template")
api.add_resource(VisionAll, "/vision") #for PLN
api.add_resource(VisionAPI, "/visionAPI")
api.add_resource(MapTemplateManual, "/GetOCRResults_Template_Manual")
api.add_resource(BbmPrediction, "/predict")  # For BBM
api.add_resource(PdamPrediction, "/predict_pdam") # For PDAM
api.add_resource(GetTextFromImage, "/get_text_image")
api.add_resource(TrainNER, "/train")
api.add_resource(LevenshteinUtils, "/levenshtein_utils")
api.add_resource(AddModel, "/add_model")
api.add_resource(ShowModel, "/show_model")
api.add_resource(ShowModelInfo, "/data/<path:model_name>")
api.add_resource(DeleteModel, "/delete_model/<string:model_name>")
api.add_resource(SelectModel, "/select_model")

if __name__ == "__main__":
    from waitress import serve
    
    serve(app, host="0.0.0.0", port=80, clear_untrusted_proxy_headers=True)
