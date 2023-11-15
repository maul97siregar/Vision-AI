"""
Custom NER Code for BBM Receipt

function:
- ner_bbm

class
- BbmPrediction
"""

import cv2
import time
import json
import werkzeug
import numpy as np

from flask import jsonify
from flask_restful import Resource, reqparse

from NawaAI.OCR import ocr
from NawaAI.NER import ner_utils
from NawaAI.NER import postprocess

from src.model_utils import load_model
from src.check_performance import check_resource

MODEL_CONFIG = "src/model_config.json"

# load model bbm
model_bbm, model_path = load_model("bbm")
print("finish load bbm model")

parser = reqparse.RequestParser()
parser.add_argument("image", type=werkzeug.datastructures.FileStorage, location="files")


def ner_bbm(nlp, debug=False, line_sensitivity=0.5, **kwargs):
    """
    named entity recognition custom for BBM receipt

    nlp: already loaded ner model
    debug: debug mode (True/False)
    line_sensitivity: text line detection sensitivity, lower means more sensitive (0 - 1)

    kwargs:
        img_cv2: img from cv2
        img_file: img path
        img_flask: img bytes from flask
        img_fastapi: img bytes or from fastapi
        img_bytes: img bytes

    returns:
        dictionary contains entities extraction
    """

    # for storing entities value
    ents_dict = {
        "KODE_SPBU": "",
        "NAMA SPBU": "",
        "LOKASI": "",
        "TANGGAL": "",
        "NO_POMPA": "",
        "NAMA_PRODUK": "",
        "HARGA_LITER": "",
        "JUMLAH_LITER": "",
        "TOTAL_HARGA": "",
        "NO_PLAT": "",
    }

    # for renaming the label
    new_label = {
        "KODE_SPBU": "spbucode",
        "NAMA SPBU": "spbuname",
        "LOKASI": "custaddress",
        "TANGGAL": "transactiondate",
        "NO_POMPA": "pumpnumber",
        "NAMA_PRODUK": "product",
        "HARGA_LITER": "rate",
        "JUMLAH_LITER": "quantity",
        "TOTAL_HARGA": "bill",
        "NO_PLAT": "customerId",
    }

    # set static value to new label
    new_label_with_value = {
        "billingtype": "Bensin",
        "custname": "",
        "listTransaction": [],
        "transactiontype": "BBM",
    }

    # define entities with number value
    number_ents = ["HARGA_LITER", "NO_POMPA"]

    # for storing final value
    new_ents_dict = {}

    # READ IMAGE FROM SOURCE
    if "img_cv2" in kwargs:
        img = kwargs.get("img_cv2")
        img_bytes = cv2.imencode(".jpg", img)[1]
        img = np.array(img_bytes).tobytes()
    elif "img_file" in kwargs:
        img = kwargs.get("img_file")
    elif "img_flask" in kwargs:
        img = kwargs.get("img_flask").read()
    elif "img_fastapi" in kwargs:
        img = kwargs.get("img_fastapi")
    elif "img_bytes" in kwargs:
        img = kwargs.get("img_bytes")
    else:
        raise KeyError("list kwargs: img, img_file, img_bytes")

    # check_resource("after get input file")
    # GET TEXT FROM VISIONAI OCR
    time_ocr = time.time()

    try:
        text_line = ocr.GetTextFromImage(img, debug=debug, sensitivity=line_sensitivity)
    except Exception as e:
        text_line = ""

    # check_resource("after get text from image")

    time_ocr = time.time() - time_ocr
    # print(f"time ocr: {time_ocr} s")

    text = " ".join(text_line)

    # VALIDATE
    key_check_spbu = ["PERTAMINA", "SPBU", "SHELL", "VIVO"]
    if not any(word in text.upper() for word in key_check_spbu):
        return {"status": "Invalid"}

    time_predict = time.time()

    # MAKE PREDICTION USING SPACY
    doc = nlp(text)

    # check_resource("after make prediction")

    # GET TIME
    time_receipt = postprocess.get_time(text)

    # GET THE RESULT TO ENTS DICT
    # untuk label entity yg memerlukan validasi setelah predict otomatis, letakkan disini
    for ent in doc.ents:
        if ent.label_ == "TANGGAL":
            clean_date = postprocess.clean_date(ent.text)
            if postprocess.date_validator(clean_date):
                ents_dict[ent.label_] = " ".join([clean_date, time_receipt])
        elif ent.label_ == "TOTAL_HARGA":
            clean_total_harga = postprocess.get_number(ent.text)
            if postprocess.currency_validator(clean_total_harga):
                ents_dict[ent.label_] = clean_total_harga.replace(",", "").replace(
                    ".", ""
                )
        else:
            ents_dict[ent.label_] = ent.text

    # JIKA ADA YG TIDAK TEREKSTRAKSI MAKA COBA MANUAL PAKAI LEVENSHTEIN
    with open("data/entities_key/key_bbm.json") as f:
        keywords = json.load(f)

    if text_line != "":
        ents_dict = ner_utils.ner_levenshtein(ents_dict, keywords, text_line)

    # check_resource("after levenshtein")

    # POST PROCESSING, DATA CLEANING
    for ent in ents_dict:
        if ent in number_ents:
            ents_dict[ent] = postprocess.get_number(ents_dict[ent])
        elif ent == "NAMA_PRODUK":
            # ents_dict[ent] = postprocess.clean_product_name(ents_dict[ent].replace("_", "").replace("-","").replace("BIOSOLAR", "BIO SOLAR").replace("BioSolar", "BIO SOLAR").replace("PERTAMAXTURBO", "PERTAMAX TURBO").replace("PERTAMAXRACING", "PERTAMAX RACING").replace("PERTAMAXPLUS", "PERTAMAX PLUS").replace("PERTAMINADEX", "PERTAMINA DEX").replace("SHELLSUPER", "SHELL SUPER").replace("SHELLVPOWER", "SHELL V POWER").replace("SHELLSUPERRON92", "SHELL SUPER RON 92").replace("SHELLVPOWERRON95", "SHELL V POWER RON 95").replace("SHELLVPOWERDIESEL", "SHELL V POWER DIESEL").replace("SHELLDIESELEXTRA", "SHELL DIESEL EXTRA").replace("SHELLVPOWERNITRO+", "SHELL V POWER NITRO+").replace("REVVO92", "REVVO 92").replace("REVVO89", "REVVO 89").replace("REVVO95", "REVVO 95").replace("REVVO90", "REVVO 90").replace(":Revvo89", "REVVO 89").replace("BP90", "BP 90").replace("BP95", "BP 95").replace("BP92", "BP 92").title())
            ents_dict[ent] = (
                postprocess.clean_product_name(ents_dict[ent])
                .replace("_", " ")
                .replace("-", " ")
                .title()
            )
            ents_dict[ent] = postprocess.remove_special_characters_with_space(
                ents_dict[ent]
            )
        elif ent == "NO_PLAT":
            ents_dict[ent] = postprocess.remove_space(ents_dict[ent])
        elif ent == "TOTAL_HARGA":
            ents_dict[ent] = (
                postprocess.get_number(ents_dict[ent]).replace(",", "").replace(".", "")
            )
        elif ent == "JUMLAH_LITER":
            ents_dict[ent] = postprocess.get_number(ents_dict[ent]).replace(",", ".")

    # rename to new label
    for key, value in ents_dict.items():
        new_ents_dict[new_label[key]] = value

    # join new label with new label with static value
    new_ents_dict = new_ents_dict | new_label_with_value

    time_predict = time.time() - time_predict

    # check_resource("after get final result")

    return new_ents_dict


class BbmPrediction(Resource):
    """
    Extract value from bbm receipt

    - get: API name
    - post: extracting value from receipt
    """

    def __init__(self):
        self.debug_mode = False

    def get(self):
        msg = "Named Entity Recognition BBM"
        return msg, 200

    def post(self):
        """
        Extract value from bbm receipt

        params:
        - file: bbm receipt image
        """

        # check if any changes in active model
        global model_path, model_bbm

        with open(MODEL_CONFIG, "r") as config_file:
            active_model = json.load(config_file)

        if active_model["bbm"] != model_path:
            print(f"changing bbm model from {model_path} to {active_model['bbm']}..")
            model_bbm, model_path = load_model("bbm")
            print("finish reload bbm model")

        args = parser.parse_args()
        file = args["image"]
        start_time = time.time()
        result = ner_bbm(
            model_bbm, img_flask=file, debug=self.debug_mode, line_sensitivity=0.2
        )
        # print(f"time bbm predict: {time.time() - start_time} s")
        return jsonify(result)
