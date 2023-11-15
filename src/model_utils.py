"""
AI Model Utilization

Function list:
- load_model

Class list:
- AddModel
- DeleteModel
- SelectModel
- ShowModel
- ShowModelInfo
"""

import os
import time
import json
import spacy
import shutil
import zipfile

from flask_restful import Resource
from flask import request, render_template, make_response

from src.utilization import is_valid_folder_name, zip_contains_file, cleanup

MODEL_FOLDER = "data/model_ner"
UPLOAD_FOLDER = "uploads"
MODEL_CONFIG = "src/model_config.json"
RECEIPT_TYPE = ["bbm", "pdam"]

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def load_model(receipt_type):
    """
    Load model

    receipt type: bbm, pdam

    return model pdam, active model location
    """
    if receipt_type not in RECEIPT_TYPE:
        return f"Error: {receipt_type} not found in {RECEIPT_TYPE}"

    with open(MODEL_CONFIG, "r") as config_file:
        active_model = json.load(config_file)
    
    model_path = active_model[receipt_type].replace('\\', '/')

    model_pdam = spacy.load(model_path)
    return model_pdam, active_model[receipt_type]


class AddModel(Resource):
    """
    Add AI model

    - get: show API name
    - post: for adding new model
    """

    def get(self):
        res = "Add Model API"
        return res, 200

    def post(self):
        """
        For adding new model

        params:
        - model_name: model name
        - file: model zip
        """
        model_name = request.form.get("model_name")

        # validate input
        if not is_valid_folder_name(model_name):
            res = {
                "error": "Enter valid model name: letters, numbers, underscores, and hyphens"
            }
            return res, 400

        model_list = [model for model in os.listdir(MODEL_FOLDER)]

        if model_name in model_list:
            res = {"error": f"Duplicate file name, {model_name} is already exist"}
            return res, 400

        if "file" not in request.files:
            res = {"error": "No file"}
            return res, 400

        file = request.files["file"]

        if file.filename == "":
            res = {"error": "No selected file"}
            return res, 400

        if not (
            "." in file.filename and file.filename.rsplit(".", 1)[1].lower() in {"zip"}
        ):
            res = {"error": f"Wrong File Extension, shoud be: .zip"}
            return res, 400

        # define zip location path
        zip_path = os.path.join(UPLOAD_FOLDER, file.filename)
        file.save(zip_path)

        # validate model zip
        if not zip_contains_file(zip_path, "meta.json"):
            res = {"error": "Not valid model"}
            cleanup(zip_path)
            return res, 400

        # extract location
        extracted_folder = os.path.join(MODEL_FOLDER, model_name)
        os.makedirs(extracted_folder, exist_ok=True)

        # extracting
        try:
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(extracted_folder)
        except Exception as e:
            res = {"error": f"Error extracting ZIP: {str(e)}"}
            return res, 500

        res = {"info": f"model uploaded, model name: {model_name}"}

        # cleanup
        # delete uploaded and extracted zip
        cleanup(zip_path)

        return res, 200


class DeleteModel(Resource):
    """
    For deleting a model

    - delete: for deleting model
    """

    def delete(self, model_name):
        """
        For deleting a model

        method:
        - delete: /delete_model/<string:model_name>
        """

        model_path = os.path.join(MODEL_FOLDER, model_name)

        try:
            shutil.rmtree(model_path)
            res = {"info": f"Successfully delete {model_name}"}
            return res
        except:
            res = {"error": "Model not found"}
            return res, 404


class SelectModel(Resource):
    """
    For selecting active model

    - get: show current active model
    - post: select/replace active model
    """

    def get(self):
        """
        For showing current active model
        """

        with open(MODEL_CONFIG, "r") as config_file:
            active_model = json.load(config_file)
        return active_model

    def post(self):
        """
        For select/replace active model

        params:
        - receipt_type: bbm, pdam
        - model_name: model name, see: /show_model
            to see model list
        """

        model_list = [model for model in os.listdir(MODEL_FOLDER)]

        receipt_type = request.form.get("receipt_type").lower()
        model_name = request.form.get("model_name")

        if receipt_type not in RECEIPT_TYPE:
            res = {"error": f"{receipt_type} is not found in {RECEIPT_TYPE}"}
            return res, 404

        if model_name not in model_list:
            res = {
                "error": f"{model_name} is not found, to see model list: /show_model"
            }
            return res, 404

        with open(MODEL_CONFIG, "r") as config_file:
            active_model = json.load(config_file)

        active_model[receipt_type] = os.path.join(MODEL_FOLDER, model_name)

        # save json
        with open(MODEL_CONFIG, "w") as json_file:
            json.dump(active_model, json_file, indent=4)

        res = {"info": f"active model {receipt_type} is changed to {model_name}"}

        return res, 200


class ShowModel(Resource):
    """
    For showing model list in server

    - get: for showing model list
    """

    def get(self):
        """
        For showing model list in server
        """

        model_list = [model for model in os.listdir(MODEL_FOLDER)]
        headers = {"Content-Type": "text/html"}

        return make_response(
            render_template("model_list.html", model_list=model_list), headers
        )


class ShowModelInfo(Resource):
    """
    For showing model info

    - get: for showing model info
    """

    def get(self, model_name):
        """
        For showing model information

        method:
        - get: /data/<path:model_name>
        """

        file_path = os.path.join("data", model_name)
        if os.path.exists(file_path) and file_path.endswith(".json"):
            with open(file_path, "r") as file:
                data = json.load(file)
            return data, 200
        else:
            res = {"error": f"File: {file_path} not found"}
            return res, 404
