"""
Named Entity Recognition with SpaCy

function list:
    - create_dataset_from_jsonl
    - train
    - evaluate
    - predict_from_text_list
    - save_model
    - load_model
    - autolabel
    - manual extraction
"""

from . import postprocess
from . import utils
import jsonlines as jsonl
import json
import random
import re
import os
import datetime
import matplotlib.pyplot as plt
import logging
import numpy as np
from Levenshtein import ratio
from jsonlines import Reader

import spacy
from spacy.util import minibatch
from spacy import displacy
from spacy.training.example import Example
from spacy.scorer import Scorer

import warnings

warnings.filterwarnings(action="once")

# Debug Status
DEBUG = False

def log(*s):
    if DEBUG:
        try:
            display(s)
        except:
            print(s)

def create_dataset_from_jsonl(in_file, percentage: list, upper=False, print_result=False):
    """
    create dataset (train, dev, and test) from jsonl format to spacy format

    in_file: jsonl file path
    percentage: list with 3 int values and sum value is 100, example: [80,10,10] train: 80%, dev: 10%, test: 10%
    upper: uppercase
    print_result: print the split result

    return:
        train_dataset: dataset for training with spacy tuple format
        dev_dataset: dataset for evaluating with spacy tuple format
        test_dataset: dataset for testing with spacy tuple format

    spacy format:
        ("text", {annotation: [0, 3, "label"]})

    """
    dataset = []

    if isinstance(in_file, str):
        with jsonl.open(in_file) as reader:
            reader = list(reader)

    elif isinstance(in_file, list):
        reader = in_file

    for obj in reader:
        if upper:
            text = obj["text"].upper()
        else:
            text = obj["text"]
        entities = {"entities": [tuple(label) for label in obj["label"]]}
        dataset.append((text, entities))

    # split train eval
    random.seed(0)
    random.shuffle(dataset)
    train_dataset, dev_dataset, test_dataset = utils.split_list_3(dataset, percentage)

    if print_result:
        print(
            f"train data: {len(train_dataset)}, dev data: {len(dev_dataset)}, test data: {len(test_dataset)}"
        )

    return train_dataset, dev_dataset, test_dataset


def train(train_data, iter_loop, drop=0.5, print_progress=False, show_graph=False):
    """
    training custom named entity recognition from stratch with spacy dataset format

    train_data: dataset for training with spacy format
    iter_loop: how many training iteration
    drop: dropout value, higher value mean the model will be more difficult to remember while training, to prevent overfitting, default 0.5
    print_progress: print iteration progress and losses
    show_graph: show losses graph at the end of training

    spacy format:
        ("text", {annotation: [0, 3, "label"]})

    returns:
        nlp: ner model
    """

    # initiate
    nlp = spacy.blank("id")
    nlp.add_pipe("ner")
    nlp.begin_training()

    ner = nlp.get_pipe("ner")
    pipe_exceptions = ["ner", "trf_wordpiecer", "trf_tok2vec"]
    unaffected_pipes = [pipe for pipe in nlp.pipe_names if pipe not in pipe_exceptions]

    # get labels
    LABELS = []
    for _, annotations in train_data:
        for ent in annotations.get("entities"):
            LABELS.append(ent[2])

    # add labels
    for label in list(set(LABELS)):
        ner.add_label(label)

    # TRAINING THE MODEL
    with nlp.disable_pipes(*unaffected_pipes):
        plot_loss = []

        for iteration in range(iter_loop):
            # shuufling examples  before every iteration
            random.shuffle(train_data)
            losses = {}

            # batch up the examples using spaCy's minibatch
            for batch in minibatch(train_data, size=2):
                for text, annotations in batch:
                    # create Example
                    doc = nlp.make_doc(text)
                    example = Example.from_dict(doc, annotations)

                    # Update the model
                    nlp.update([example], losses=losses, drop=drop)

            plot_loss.append(losses["ner"])

            if print_progress:
                print(f"Losses at iteration {iteration} {losses}")

    # plot losses
    if show_graph:
        _, ax = plt.subplots()

        ax.plot(plot_loss)

        ax.set_title("Loss Value during Iteration")
        ax.set_xlabel("Iter")
        ax.set_ylabel("Loss")

        plt.show()

    return nlp


def evaluate(nlp, eval_dataset, upper=False):
    """
    for evaluating the model

    nlp: ner model
    eval_dataset: the dataset for evaluating with spacy dataset format
    upper: uppercase

    spacy format:
        ("text", {annotation: [0, 3, "label"]})

    returns:
        ner scores json
    """

    examples = []
    scorer = Scorer()

    for text, annotations in eval_dataset:
        if upper:
            text = text.upper()
        doc = nlp.make_doc(text)
        example = Example.from_dict(doc, annotations)
        example.predicted = nlp(str(example.predicted))
        examples.append(example)

    scores = scorer.score(examples)

    return scores


def predict_from_text_list(nlp, texts: list, display=True):
    """
    predict ner from list of text

    nlp: ner model
    texts: list of text
    display: show result, default True

    returns:
        list dict of entity label and entity text
    """
    result = []

    for text in texts:
        doc = nlp(text)

        if display:
            displacy.render(doc, style="ent")

        dict_data = {}

        for ent in doc.ents:
            dict_data[ent.label_] = ent.text

        result.append(dict_data)

    return result


def save_model(out_folder, nlp, print_result=False):
    """
    saving the model

    out_folder: output folder location
    nlp: ner model

    returns:
        saved model in folder: checkpoint_ner_{date_time}
    """

    utils.create_folder(out_folder)

    now = datetime.datetime.now()
    date_time = now.strftime("%d-%m-%Y-%H-%M")

    model_name = f"checkpoint_ner_{date_time}"
    folder_model_path = os.path.join(out_folder, model_name)

    utils.create_folder(folder_model_path)

    nlp.to_disk(folder_model_path)
    print(f"Saved model to {folder_model_path}")

    return folder_model_path


def load_model(in_folder):
    """
    loading spacy model from folder path

    in_folder: model folder location

    return:
        nlp ner model
    """
    nlp = spacy.load(in_folder)
    print(f"Model loaded from {in_folder}")

    return nlp


def autolabel(texts, nlp, out_folder, display=False):
    """
    autolabeling from text list

    get a lot new dataset? let's label with
    autolabel to speed up the process

    texts: list of texts
    nlp: ner model
    out_folder: output folder path
    display: for displaying ents with displacy, default False

    returns:
        dataset: list of json of text and labels
        file: autolabel_{date_time}.jsonl
    """

    dataset = []
    for text in texts:
        doc = nlp(text)
        dict_data = {}
        for ent in doc.ents:
            dict_data[ent.label_] = ent.text
            data = {
                "text": text,
                "label": [
                    [ent.start_char, ent.end_char, ent.label_] for ent in doc.ents
                ],
            }

        dataset.append(data)

        if display == True:
            displacy.render(doc, style="ent")

    utils.create_folder(out_folder)

    now = datetime.datetime.now()
    date_time = now.strftime("%d-%m-%Y-%H-%M")

    fname = os.path.join(out_folder, f"autolabel_{date_time}.jsonl")

    with open(fname, "w") as f:
        for item in dataset:
            f.write(json.dumps(item) + "\n")

    print(f"saved at {fname}")

    return dataset


def ner_manual(ent_result: dict, keywords: dict, text_line: list):
    """
    manual entity extraction, strict method

    mendapatkan nilai dengan mencari kata kunci di dalam text
    contoh:
        text: "nama : udin"
        kata kunci: "nama"
        hasil: "udin"

    cara kerja:
        lakukan cleansing (:), menjadi "nama udin"
        cari apakah ada kata kunci di dalam text tersebut, "nama" in "nama udin" = True
        apabila ada, maka ambil kata setelah kata kunci, yaitu "udin"
        sehingga hasil akhirnya adalah "udin"

    arg:
        ent_result: dictionary berisi label entities, contoh: {"nama": "udin", "pekerjaan": "programmer"}
        keywords: dictionary berisi keyword dari suatu label, contoh: {"nama": ["nama pelanggan", "nama"], "pekerjaan": ["pekerjaan saat ini", "pekerjaan"]}
        text_line: list berisi text line-per-line, contoh: ["nama: udin", "pekerjaan: programmer"]

    return:
        ent_result yang sudah diisi dengan metode ini
    """
    # clean special character
    text_line = [text.replace(":", "") for text in text_line]

    for ent in ent_result:
        if ent_result[ent] == "" and ent in keywords:
            # jika ent_result tidak ada maka cari dengan keywordnya
            for label in keywords:
                for key in keywords[label]:
                    for text in text_line:
                        if key.lower() in text.lower():
                            # jika keyword ada di text maka cari indexnya
                            index = postprocess.find_string_index(
                                text.lower(), key.lower()
                            )
                            if index != -1:
                                # split text menjadi kata per kata
                                words = text.split()
                                # ambil kata dengan index + 1 dan seterusnya
                                value = " ".join(words[index + 1 :])
                                ent_result[label] = value
    return ent_result


def contains_number(text):
    pattern = r"\d"  # regular expression pattern to match any digit
    return bool(re.search(pattern, text))


def find_max_indexes(nested_list):
    max_value = float("-inf")  # Inisialisasi dengan nilai terkecil
    max_indexes = []

    for i, sublist in enumerate(nested_list):
        for j, subsublist in enumerate(sublist):
            for k, value in enumerate(subsublist):
                if value > max_value:
                    max_value = value
                    max_indexes = [(i, j, k)]
                elif value == max_value:
                    max_indexes.append((i, j, k))

    return max_indexes


def ner_levenshtein(
    ent_result: dict,
    keywords: dict,
    text_line: list,
    number=[],
    max_idx_number_find=None,
    key_on_first=[],
    key_is_value=[],
    threshold=0.8,
):
    """
    manual entity extraction using Levenshtein, more flexible method

    mendapatkan nilai dengan mencari kata kunci yang mirip-
    berdasarkan ratio levenshtein di dalam text

    dengan ini maka bisa mencari nilai meskipun keywordnya terdapat typo
    contoh:
        text: "nam4 : udin"
        kata kunci: "nama"
        hasil: "udin"

    cara kerja:
        lakukan cleansing (:), menjadi "nam4 udin"
        hitung rasio kemiripan antara kata kunci dengan setiap kata di dalam text, "nama" >> "nam4" = 0.75, "nama" >> "udin" = 0.0
        kata yang mirip dengan kata kunci akan memiliki rasio yang tinggi, skala (0.0 - 1.0)
        cari letak kata yang memiliki rasio yang tinggi, yaitu "nama4" dengan index 0
        lalu ambil kata setelahnya dengan index setelahnya, yaitu "udin"
        hasil akhirnya adalah "udin"

    arg:
        ent_result: dictionary berisi label entities, contoh: {"nama": "udin", "pekerjaan": "programmer"}
        keywords: dictionary berisi keyword dari suatu label, contoh: {"nama": ["nama pelanggan", "nama"], "pekerjaan": ["pekerjaan saat ini", "pekerjaan"]}
        text_line: list berisi text line-per-line, contoh: ["nama: udin", "pekerjaan: programmer"]
        number: list berisi label entities yang memiliki value number, contoh: total harga
        max_idx_number_find: maksimum ditemukannya number di index keberapa setelah key, contoh: pemakaian 62, pemakaian adalah keynya, numbernya berada di index ke 0 setelah key, max index >= 0 bisa mendapatkan nilai tsb
        key_on_first: list berisi label/key yang letaknya diawal baris, baru support 1 kata saja, contoh: periode feb 2023, key: periode
        key_is_value: list berisi label/key yang sama dengan valuenya, baru support 1 kata saja, contoh pada kasus merchant, key: pos value: pos

    return:
        ent_result yang sudah diisi dengan metode ini
    """
    # clean special character
    text_line = [text.replace(":", "").replace("=", "") for text in text_line]
    for ent in ent_result:
        if ent_result[ent] == "" and ent in keywords:
            # untuk menyimpan ratio dari semua keyword
            keywords_ratio = []
            for key in keywords[ent]:
                # dapatkan jumlah kata pada key
                len_word_key = len(key.split())
                # untuk menyimpan ratio dari satu keyword
                keyword_ratio = []
                for text in text_line:
                    # untuk entities number, check text berisi angka atau tidak
                    if ent in number and not contains_number(text):
                        # jika tidak ada angka maka text ratio 0 semua
                        text_ratio = [0 for _ in range(len(text.split()))]
                    else:
                        # tokenisasi text
                        text_token = text.split()
                        # dapatkan jumlah kata pada text token
                        len_word_text = len(text_token)
                        # hitung jumlah perulangan
                        token_loop_size = len_word_text - len_word_key + 1
                        # untuk menyimpan ratio dari suatu text line
                        text_ratio = []
                        # loop sebanyak jumlah perulangan
                        for i in range(token_loop_size):
                            # apabila jumlah kata pada key tidak sama dengan 1,
                            # maka tambahkan ratio 0.0 sejumlah kata pada key - 1
                            if len_word_key != 1:
                                if i == 0:
                                    for _ in range(len_word_key - 1):
                                        text_ratio.append(0.0)
                                # ambil kata dari tokenisasi untuk di compare sejumlah banyaknya kata di key
                                word_compare = " ".join(
                                    text_token[i : i + (len_word_key)]
                                )
                            else:
                                # apabila jumlah kata pada key sama dengan 1,
                                # maka kata untuk di compare sejumlah 1 juga
                                word_compare = text_token[i]
                            # hitung ratio kemiripan antara key dan kata
                            key_text_ratio = ratio(key.lower(), word_compare.lower())
                            # masukkan nilai ratio ke text ratio
                            text_ratio.append(key_text_ratio)
                    # masukkan ratio dari suatu text line ke keyword ratio
                    keyword_ratio.append(text_ratio)
                # masukkan keyword ratio ke keywords ratio
                keywords_ratio.append(keyword_ratio)

            # karena jumlah text dari suatu line tidak sama,
            # sehingga jumlah item hasil perhitungan rationya juga tidak sama,
            # maka samakan jumlah item di keywords_ratio
            max_len = max(
                len(sublst) for sublist in keywords_ratio for sublst in sublist
            )
            for sublist in keywords_ratio:
                for sublst in sublist:
                    while len(sublst) < max_len:
                        sublst.append(0.0)

            # Convert ke numpy array dan temukan index dari max value-nya
            arr = np.array(keywords_ratio)
            # Thresholding
            arr[arr < threshold] = 0.0
            # Cek apakah setelah thresholding semua array bernilai 0.0
            if not np.all(arr == 0.0):
                if ent in key_on_first:
                    max_indexes = find_max_indexes(arr)

                    for max_index in max_indexes:
                        if max_index[2] == 0:
                            _, text_line_index, word_index = max_index
                            break

                    # dapatkan value dari key nya
                    words = text_line[text_line_index].split()
                    value = " ".join(words[word_index + 1 :])

                    ent_result[ent] = value

                elif ent in key_is_value:
                    arr[arr < 1] = 0.0

                    if not np.all(arr == 0.0):
                        max_indexes = find_max_indexes(arr)

                        _, text_line_index, word_index = max_indexes[0]

                        words = text_line[text_line_index].split()
                        value = words[word_index]

                        ent_result[ent] = value
                    else:
                        ent_result[ent] = ""

                elif ent in number and max_idx_number_find != None:
                    max_index = np.unravel_index(np.argmax(arr), arr.shape)
                    _, text_line_index, word_index = max_index

                    text_number = text_line[text_line_index].split()[word_index+1:word_index+2+max_idx_number_find]
                    value = " ".join(text_number)

                    log(f"ent: {ent}, max_idx_number_find: {max_index}, text_line: {text_line[text_line_index]}")
                    log(f"{text_number, value}")

                    if contains_number(value):
                        ent_result[ent] = value
                    else:
                        ent_result[ent] = ""

                    log(f"result max number: {value}")

                else:
                    # Get max index
                    max_index = np.unravel_index(np.argmax(arr), arr.shape)

                    # keyword index keberapa, line text keberapa, dan word index keberapa
                    _, text_line_index, word_index = max_index

                    # display(arr, (key_index, text_line_index, word_index))

                    # dapatkan value dari key nya
                    words = text_line[text_line_index].split()
                    value = " ".join(words[word_index + 1 :])

                    ent_result[ent] = value

                    # if ent == "PEMAKAIAN" or ent == "METER_AWAL":
                    #     print(ent, max_index)

            else:
                ent_result[ent] = ""

    return ent_result
