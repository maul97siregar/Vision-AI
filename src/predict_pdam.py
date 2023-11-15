"""
Custom NER Code for BBM Receipt

function:
- ner_pdam

class
- PdamPrediction
"""

import cv2
import time
import json
import werkzeug
import numpy as np

from flask import jsonify
from flask_restful import Resource, reqparse

from Levenshtein import ratio

from NawaAI.OCR import ocr
from NawaAI.NER import postprocess
from NawaAI.NER import ner_utils

from src.model_utils import load_model

MODEL_CONFIG = "src/model_config.json"

model_pdam, model_path = load_model("pdam")
print("finish load pdam model")

parser = reqparse.RequestParser()
parser.add_argument("image", type=werkzeug.datastructures.FileStorage, location="files")


def ner_pdam(nlp, debug=False, line_sensitivity=0.5, **kwargs):
    """
    named entity recognition - PDAM

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

    # max index number find
    MAX_IDX_NUMBER = 2

    # for storing entities value
    ents_dict = {
        "TANGGAL_PEMBAYARAN": "",
        "NAMA_PELANGGAN": "",
        "ALAMAT_PELANGGAN": "",
        "GOLONGAN": "",
        "NAMA_PDAM": "",
        "PERIODE": "",
        "PEMAKAIAN": "",
        "TOTAL_TAGIHAN": "",
        "NO_PELANGGAN": "",
        "METER_AWAL": "",
        "METER_AKHIR": "",
        "METER_AWAL_AKHIR": "",
        "MERCHANT": "",
    }

    # for renaming the label
    new_label = {
        "ALAMAT_PELANGGAN": "custaddress",
        "TANGGAL_PEMBAYARAN": "transactiondate",
        "TOTAL_TAGIHAN": "bill",
        "NO_PELANGGAN": "customerId",
        "NAMA_PELANGGAN": "custname",
        "PERIODE": "periode",
        "METER_AWAL": "meter_awal",
        "METER_AKHIR": "meter_akhir",
        "PEMAKAIAN": "quantity",
        "MERCHANT": "merchant",
        "GOLONGAN": "type",
        "NAMA_PDAM": "pdamname",
        "METER_AWAL_AKHIR": "meter_awal_akhir",
    }

    # set static value to new label
    new_label_with_value = {
        "billingtype": "PDAM_Postpaid",
        "listTransaction": [],
        "transactiontype": "WATER",
        "product": "Water",
        "rate": "",
    }

    # to remove the prefix value from a value
    pre = {
        "GOLONGAN": [
            "GOL TARIF",
            "KODE TARIF",
            "KODE TARIF",
            "RATE TYPE",
            "KODE GOL",
            "JENIS TARIF",
            "GOLONGAN",
            "GOL",
            "TARIF",
            "KELOMPOK",
        ],
        "ALAMAT_PELANGGAN": ["ALAMAT"],
        "NAMA_PELANGGAN": ["NAMA PELANGGAN", "PELANGGAN", "NAMA"],
    }

    ents = ["NAMA_PELANGGAN", "ALAMAT_PELANGGAN", "GOLONGAN"]

    # entities with number value
    ents_number = [
        "NO_PELANGGAN",
        "TOTAL_TAGIHAN",
        "PEMAKAIAN",
        "METER_AWAL",
        "METER_AKHIR",
    ]

    # entities with the key in the front of text line
    ents_key_on_first = ["PERIODE"]

    # entities with the key is the value
    key_is_value = ["MERCHANT"]

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

    # GET TEXT FROM VISIONAI OCR
    time_ocr = time.time()

    try:
        text_line = ocr.GetTextFromImage(img, debug=debug, sensitivity=line_sensitivity)
    except Exception as e:
        text_line = ""

    time_ocr = time.time() - time_ocr
    # print(time_ocr)

    text = " ".join(text_line)

    # VALIDATE
    key_check_pdam = ["PDAM", "AIR", "PAM", "POS", "INDOMARET", "ALFAMART"]
    if not any(word in text.upper() for word in key_check_pdam):
        return {"status": "Invalid"}

    # GET TIME
    time_receipt = postprocess.get_time(text)

    time_predict = time.time()

    # MAKE PREDICTION USING SPACY
    doc = nlp(text.upper())

    # GET THE RESULT TO ENTS DICT
    # untuk label entity yg memerlukan validasi setelah predict otomatis, letakkan disini
    for ent in doc.ents:
        if ent.label_ == "TANGGAL_PEMBAYARAN":
            clean_date = postprocess.clean_date(ent.text)
            if postprocess.date_validator(clean_date):
                ents_dict[ent.label_] = " ".join([clean_date, time_receipt])
        elif ent.label_ == "TOTAL_TAGIHAN":
            if not ents_dict[ent.label_]:
                clean_total_tagihan = postprocess.get_number(ent.text)
                if postprocess.currency_validator(clean_total_tagihan):
                    clean_total_tagihan = postprocess.clean_currency_decimal(
                        clean_total_tagihan
                    )
                    ents_dict[ent.label_] = clean_total_tagihan.replace(
                        ",", ""
                    ).replace(".", "")
                
        elif ent.label_ == "METER_AWAL_AKHIR":
            meter_awal_akhir_list_value = postprocess.get_list_number(ent.text)
            if len(meter_awal_akhir_list_value) >= 2:
                ents_dict["METER_AWAL_AKHIR"] = meter_awal_akhir_list_value
        else:
            ents_dict[ent.label_] = ent.text

    # UNTUK EKSTRAK PAM LYONNAISE METER AWAL, METER AKHIR, PEMAKAIAN
    if "lyonnaise" in text.lower():
        for idx, line in enumerate(text_line):
            key_text_ratio = ratio(line[:10].lower(), "Stand Awal".lower())
            if key_text_ratio > 0.9:
                pemakaian_lyonnaise = text_line[idx + 1]
                break

        meter_awal, meter_akhir, pemakaian = pemakaian_lyonnaise.split(" ")[:3]
        ents_dict["METER_AWAL"] = meter_awal.replace(".", "")
        ents_dict["METER_AKHIR"] = meter_akhir.replace(".", "")
        ents_dict["PEMAKAIAN"] = pemakaian.replace(".", "")

    # POST PROCESSING, DATA CLEANING 1
    for ent in ents_dict:
        if ent in ents_number:
            ents_dict[ent] = postprocess.get_number(ents_dict[ent])

    # FOR FILLING PEMAKAIAN 1
    # if (
    #     not ents_dict["PEMAKAIAN"]
    #     or not ents_dict["METER_AWAL"]
    #     or not ents_dict["METER_AKHIR"]
    # ):
    #     if ents_dict["METER_AWAL"] and ents_dict["METER_AKHIR"]:
    #         ents_dict["PEMAKAIAN"] = int(
    #             ents_dict["METER_AKHIR"].replace(",", "").replace(".", "")
    #         ) - int(ents_dict["METER_AWAL"].replace(",", "").replace(".", ""))
    #     elif ents_dict["METER_AWAL_AKHIR"]:
    #         if len(ents_dict["METER_AWAL_AKHIR"]) == 3:
    #             ents_dict["METER_AWAL"] = ents_dict["METER_AWAL_AKHIR"][0]
    #             ents_dict["METER_AKHIR"] = ents_dict["METER_AWAL_AKHIR"][1]
    #             ents_dict["PEMAKAIAN"] = ents_dict["METER_AWAL_AKHIR"][2]
    #         if len(ents_dict["METER_AWAL_AKHIR"]) == 2:
    #             ents_dict["METER_AWAL"] = ents_dict["METER_AWAL_AKHIR"][0]
    #             ents_dict["METER_AKHIR"] = ents_dict["METER_AWAL_AKHIR"][1]
    #             ents_dict["PEMAKAIAN"] = (
    #                 ents_dict["METER_AWAL_AKHIR"][1] - ents_dict["METER_AWAL_AKHIR"][0]
    #             )

    # JIKA ADA YG TIDAK TEREKSTRAKSI MAKA COBA MANUAL PAKAI LEVENSHTEIN
    with open("data/entities_key/key_pdam.json") as f:
        keywords = json.load(f)

    if text_line != "":
        ents_dict = ner_utils.ner_levenshtein(
            ents_dict,
            keywords,
            text_line,
            number=ents_number,
            max_idx_number_find=MAX_IDX_NUMBER,
            key_on_first=ents_key_on_first,
            key_is_value=key_is_value,
        )
        

    # JIKA MERCHANT TIDAK ADA
    merchant = [
        "INDOMARET",
        "ALFAMART",
        "POS",
        "POS INDONESIA",
        "TOKOPEDIA",
        "OCTO",
        "PALYJA",
    ]
    if not ents_dict["MERCHANT"]:
        ents_dict["MERCHANT"] = [
            merch if merch.lower() in text.lower() else "" for merch in merchant
        ][0]

    # POST PROCESSING, DATA CLEANING 2
    for ent in ents_dict:
        if ent in ents_number:
            ents_dict[ent] = postprocess.get_number(ents_dict[ent])
        if ent in ents:
            ents_dict[ent] = postprocess.get_word_after_colon_or_remove_preffix(
                ents_dict[ent], pre[ent]
            )
        if ent == "PERIODE":
            ents_dict[ent] = postprocess.clean_month_year(ents_dict[ent])
        if ent == "TOTAL_TAGIHAN":
            ents_dict[ent] = (
                postprocess.get_number(ents_dict[ent]).replace(",", "").replace(".", "")
            )

    # DATA CLEANING IF PEMAKAIAN: ddd-ddd=ddd OR ddd-ddd
    if not ents_dict["PEMAKAIAN"].isnumeric():
        pemakaian = ents_dict["PEMAKAIAN"]

        pemakaian = "".join(
            [
                char.replace(char, " ") if not char.isnumeric() else char
                for char in pemakaian
            ]
        )
        pemakaian = pemakaian.split()

        if len(pemakaian) == 3:
            ents_dict["METER_AWAL"] = pemakaian[0]
            ents_dict["METER_AKHIR"] = pemakaian[1]
            ents_dict["PEMAKAIAN"] = pemakaian[2]
        elif len(pemakaian) == 2:
            ents_dict["METER_AWAL"] = pemakaian[0]
            ents_dict["METER_AKHIR"] = pemakaian[1]
            

    #IF METER AWAL & AKHIR NULL GET FROM METER AWAL AKHIR
    if (not ents_dict["METER_AWAL"]
        or not ents_dict["METER_AKHIR"] and ents_dict["METER_AWAL_AKHIR"]
    ):
        if ents_dict["METER_AWAL_AKHIR"]:
            if len(ents_dict["METER_AWAL_AKHIR"]) == 3:
                ents_dict["METER_AWAL"] = str(ents_dict["METER_AWAL_AKHIR"][0])
                ents_dict["METER_AKHIR"] = str(ents_dict["METER_AWAL_AKHIR"][1])
            if len(ents_dict["METER_AWAL_AKHIR"]) == 2:
                ents_dict["METER_AWAL"] = str(ents_dict["METER_AWAL_AKHIR"][0])
                ents_dict["METER_AKHIR"] = str(ents_dict["METER_AWAL_AKHIR"][1])
    
    
    # FOR FILLING PEMAKAIAN 2
    # if (
    #     not ents_dict["PEMAKAIAN"]
    #     and ents_dict["METER_AWAL"]
    #     and ents_dict["METER_AKHIR"]
    # ):
    #     ents_dict["PEMAKAIAN"] = int(
    #         ents_dict["METER_AKHIR"].replace(",", "").replace(".", "")
    #     ) - int(ents_dict["METER_AWAL"].replace(",", "").replace(".", ""))

    # VALIDATE PEMAKAIAN

    # if ents_dict["METER_AWAL"] and ents_dict["METER_AKHIR"] and ents_dict["PEMAKAIAN"]:
    #     if int(ents_dict["METER_AKHIR"]) - int(ents_dict["METER_AWAL"]) != int(ents_dict["PEMAKAIAN"].replace(",", "").replace(".", "")):
    #         ents_dict["PEMAKAIAN"] = int(ents_dict["METER_AKHIR"]) - int(ents_dict["METER_AWAL"])

    # if ents_dict["METER_AWAL"] and ents_dict["METER_AKHIR"]:
    #     if int(ents_dict["METER_AWAL"]) > int(ents_dict["METER_AKHIR"]):
    #         temp = int(ents_dict["METER_AWAL"])
    #         ents_dict["METER_AWAL"] = int(ents_dict["METER_AKHIR"])
    #         ents_dict["METER_AKHIR"] = temp

    # rename to new label
    for key, value in ents_dict.items():
        new_ents_dict[new_label[key]] = value

    # join new label with new label with static value
    new_ents_dict = new_ents_dict | new_label_with_value

    time_predict = time.time() - time_predict
    
    print(text)
    print("RESUKT : ", new_ents_dict)
    return new_ents_dict


class PdamPrediction(Resource):
    """
    Extract value from pdam receipt

    - get: API name
    - port: extracting value from receipt
    """

    def __init__(self):
        self.debug_mode = False

    def get(self):
        msg = "Named Entity Recognition PDAM"
        return msg, 200

    def post(self):
        """
        Extract value from pdam receipt

        params:
        - file: pdam receipt image
        """

        # check if any changes in active model
        global model_path, model_pdam

        with open(MODEL_CONFIG, "r") as config_file:
            active_model = json.load(config_file)

        if active_model["pdam"] != model_path:
            print(f"changing pdam model from {model_path} to {active_model['pdam']}..")
            model_pdam, model_path = load_model("pdam")
            print("finish reload pdam model")

        args = parser.parse_args()
        file = args["image"]

        start_time = time.time()
        result = ner_pdam(
            model_pdam, img_flask=file, debug=self.debug_mode, line_sensitivity=0.2
        )
        # print(f"result pdam time: {time.time() - start_time}")
        return jsonify(result)
