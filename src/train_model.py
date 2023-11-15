"""
For training new model

Class list:
- TrainNER
"""

import os
import json
import datetime

from flask import request, jsonify, send_file
from flask_restful import Resource
from jsonlines import Reader

from NawaAI.NER.ner_utils import train, create_dataset_from_jsonl, evaluate, save_model
from src.utilization import zip_folder, delete_contents_of_folder, cleanup


class TrainNER(Resource):
    """
    For training a new AI model

    - get: API name
    - post: to train new model
    """

    def get(self):
        """
        Train NER
        """

        msg = "Train NER"
        return msg, 200

    def post(self):
        """
        Train new NER model

        dataset: dataset from doccano, jsonl format
        split: split percentage train data and test data, the sum of splits must be 100%, default [80, 20]
        iteration: how much train iteration/epoch/loop, default 20
        dropout: dropout value, default 0.6

        """

        # output folder
        OUTPUT_FOLDER = "new_models"
        os.makedirs(OUTPUT_FOLDER, exist_ok=True)

        # get the input value
        iteration = request.form.get("iteration", 10)
        dropout = request.form.get("dropout", 0.5)
        train_split = request.form.get("train_split", 0.8)

        # validate input
        if not (iteration and dropout and train_split):
            res = {"error": "The value cannot be empty"}
            return res, 400

        try:
            iteration = int(iteration)
            dropout = float(dropout)
            train_split = float(train_split)

            if not (
                iteration > 0
                and dropout >= 0
                and dropout <= 1
                and train_split >= 0.1
                and train_split <= 0.9
            ):
                raise ValueError(
                    "Wrong value, iteration: int, dropout: 0 - 1 float, train_split: 0.1 - 0.9 float"
                )

        except ValueError:
            res = {
                "error": "Wrong value, iteration: 0 - positive int, dropout: 0 - 1 float, train_split: 0.1 - 0.9 float"
            }
            return res, 400

        # get dataset file
        file = request.files["dataset"]

        # validate dataset input
        if file.filename == "":
            res = {"error": "Empyt Filename"}
            return res, 400

        if not (
            "." in file.filename
            and file.filename.rsplit(".", 1)[1].lower() in {"jsonl"}
        ):
            res = {"error": f"Wrong File Extension, shoud be: .jsonl"}
            return res, 400

        dataset = []
        with Reader(file) as reader:
            for obj in reader:
                dataset.append(obj)

        if len(dataset) == 0:
            res = {"error": f"Dataset cannot empty"}
            return res, 400

        # calculate split value
        split = [train_split * 100, 100 - (train_split * 100)]

        # create dataset
        train_dataset, _, test_dataset = create_dataset_from_jsonl(
            dataset, percentage=[split[0], 0, split[1]], upper=True, print_result=True
        )

        # dataset validation
        if len(train_dataset) == 0 or len(test_dataset) == 0:
            res = {"error": f"train_dataset or test_dataset cannot be 0"}
            return jsonify(res)

        # training
        model = train(
            train_dataset,
            iter_loop=iteration,
            drop=dropout,
            print_progress=True,
            show_graph=False,
        )

        # evaluating
        evaluate_score = evaluate(model, eval_dataset=test_dataset, upper=True)

        # saving model
        saved_model_path = save_model(
            nlp=model, out_folder=OUTPUT_FOLDER, print_result=False
        )

        # create model info
        now = datetime.datetime.now()
        train_date = now.strftime("%d-%m-%Y_%H-%M")

        evaluate_score["iteration"] = iteration
        evaluate_score["dropout"] = dropout
        evaluate_score["train_split"] = train_split
        evaluate_score["date_trained"] = train_date
        evaluate_score["train_data"] = train_dataset
        evaluate_score["test_data"] = test_dataset

        # save model info
        score_fname = "model_info.json"
        with open(os.path.join(saved_model_path, score_fname), "w") as f:
            f.write(json.dumps(evaluate_score))

        # zip model
        zip_fname = f"model_{train_date}.zip"
        zip_folder(saved_model_path, zip_fname)

        return_data = cleanup(zip_fname)

        delete_contents_of_folder(OUTPUT_FOLDER)

        # create response
        response = send_file(
            return_data, mimetype="application/zip", download_name=zip_fname
        )

        return response
