"""
For configuring dictionary based
levenshtein

Class list:
- LevenshteinUtils
"""

import json

from flask_restful import Resource
from flask import request


class LevenshteinUtils(Resource):
    """
    Levenshtein utilization

    - get: for showing levenshtein key dictionary
    - post: for configuring levenshtein key dictionary
        - add key
        - remove key
    """

    BBM_KEY = r"data\entities_key\key_bbm.json"
    PDAM_KEY = r"data\entities_key\key_pdam.json"

    def get(self):
        """
        For showing levenshtein key dictionary
        """

        result_json = {}

        with open(self.BBM_KEY, "r") as file:
            bbm_data = json.load(file)

        with open(self.PDAM_KEY, "r") as file:
            pdam_data = json.load(file)

        result_json["bbm_key_dictionary"] = bbm_data
        result_json["pdam_key_dictionary"] = pdam_data
        return result_json

    def post(self):
        """
        For add/delete key in field bbm / pdam

        params:
        - receipt_type: bbm, pdam
        - field: see API with get method
        - key: key/label to be added
        - method: add, delete
        """

        METHOD_LIST = ["add", "delete"]
        RECEIPT_LIST = ["bbm", "pdam"]

        receipt_type = request.form.get("receipt_type")
        field = request.form.get("field")
        key = request.form.get("key")
        method = request.form.get("method")

        key = key.strip()
        
        # validate input
        if (
            (method.lower() not in METHOD_LIST)
            or (receipt_type.lower() not in RECEIPT_LIST)
            or key == ""
        ):
            res = {
                "error": f"Wrong value, method: {METHOD_LIST}, receipt_type: {RECEIPT_LIST}, key cannot be empty"
            }
            return res, 400

        if receipt_type.lower() == "bbm":
            json_location = self.BBM_KEY
            with open(self.BBM_KEY, "r") as file:
                json_data = json.load(file)

        elif receipt_type.lower() == "pdam":
            json_location = self.PDAM_KEY
            with open(self.PDAM_KEY, "r") as file:
                json_data = json.load(file)

        # validate field
        if field.upper() not in json_data.keys():
            res = {
                "error": f"Wrong field in {receipt_type}, field list: {json_data.keys()}"
            }
            return res, 400

        # add
        if method.lower() == "add":
            if not (key.upper() in [k.upper() for k in json_data[field.upper()]]):
                json_data[field.upper()].append(key.upper())
                
                # sorting
                json_data[field.upper()] = sorted(json_data[field.upper()], key=lambda x: len(x.split()), reverse=True)

                res = {
                    "info": f"{key.upper()} successfully added to {field.upper()} in {receipt_type}"
                }
            else:
                res = {"error": f"{key.upper()} is already exist"}
                return res, 400

        # delete
        elif method.lower() == "delete":
            if not (key.upper() in [k.upper() for k in json_data[field.upper()]]):
                res = {"error": f"{key} in {field.upper()} not exist"}
                return res, 400
            else:
                json_data[field.upper()].remove(key.upper())
                res = {
                    "info": f"{key.upper()} successfully deleted from {field.upper()} in {receipt_type}"
                }

        # save json
        with open(json_location, "w") as json_file:
            json.dump(json_data, json_file, indent=4)

        return res
