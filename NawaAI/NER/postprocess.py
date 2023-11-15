"""
Apply postprocessing after prediction

List postprocessing:
- remove_special_characters_with_space
- remove_special_characters
- find_string_index
- date_validator
- currency_validator
- clean_currency_decimal
- get_number
- get_word_after_colon
- remove space
- clean_date
- clean_month_year
- clean_product_name (bbm)
- get_word_after_colon_or_remove_preffix
- get_list_number
- get time
"""
import re
from datetime import datetime

month_dict = {
    "januari": "01",
    "februari": "02",
    "maret": "03",
    "april": "04",
    "mei": "05",
    "juni": "06",
    "juli": "07",
    "agustus": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "desember": "12",
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "mei": "05",
    "jun": "06",
    "jul": "07",
    "agu": "08",
    "sept": "09",
    "okt": "10",
    "nov": "11",
    "des": "12",
    "january": "01",
    "february": "02",
    "march": "03",
    "april": "04",
    "may": "05",
    "june": "06",
    "july": "07",
    "august": "08",
    "september": "09",
    "october": "10",
    "november": "11",
    "december": "12",
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

import re


def remove_special_characters_with_space(text):
    pattern = r"[^a-zA-Z0-9\s]"
    cleaned_text = re.sub(pattern, " ", text)

    return cleaned_text


def remove_special_characters(text):
    # Matches any character that is not alphanumeric or whitespace
    pattern = r"[^a-zA-Z0-9\s]"
    cleaned_text = re.sub(pattern, "", text)
    return cleaned_text


def find_string_index(text, string):
    words = text.split()
    for i, word in enumerate(words):
        if word == string:
            return i
    return -1


def date_validator(text):
    try:
        datetime.strptime(text, "%d-%m-%Y")
        return True
    except ValueError:
        return False


def currency_validator(text):
    """
    validate currency
    """
    if len(text) >= 4:
        return True
    else:
        return False

def clean_currency_decimal(text):
    """
    cleaning currency
    example: IDR 691,440.00' -> 691,440
    """
    if "," in text and "." in text:
        comma_idx = text.find(",")
        period_idx = text.find(".")

        if period_idx > comma_idx:
            idx_decimal = period_idx
        else:
            idx_decimal = comma_idx
        
        if len(text[idx_decimal:]) == 3:
            text = text[:idx_decimal]

    return text

def get_number(text: str):
    """
    get number in text with .,- in between
    example: 123-123
    """
    try:
        text = str(text)
        pattern = r"\d[\d.,-]*(?:\b|(?=\w))"
        match = re.search(pattern, text.replace(" ", ""))
        num = match.group()
        return num
    except:
        return ""


def get_word_after_colon(text: str):
    """
    get last word in text
    """
    try:
        return text.split(":")[-1:][0].strip()
    except:
        return text


def remove_space(text: str):
    """
    remove space in text
    """
    try:
        return "".join(text.split())
    except:
        return text


def clean_date(text: str):
    """
    date cleaning to dd-mm-yyyy format
    """

    format = ["%d %m %y", "%d %m %Y", "%Y %m %d", "%y %m %d", "%m %d %Y"]

    try:
        if any(c.isalpha() for c in text):
            for key in month_dict.keys():
                text = text.lower().replace(key, "999" + month_dict[key])

        text = re.sub("[a-zA-Z,\\.\\-\\/'\\s]", " ", text)
        text = re.sub(" +", " ", text).strip()

        text = text.split(" ")

        if "999" in text[0]:
            text[0] = text[0][3:]
            temp = text[1]
            text[1] = text[0]
            text[0] = temp
        else:
            for i, t in enumerate(text):
                if "999" in t:
                    text[i] = text[i][3:]

        text = " ".join(text)

        for f in format:
            try:
                text = datetime.strptime(text, f).strftime("%d-%m-%Y")
                return text
            except Exception as err:
                # print(err)
                pass
        return ""

    except:
        return ""


def clean_month_year(text: str):
    """
    month year cleaning to mm-yyyy format
    """

    format = ["%m %y", "%m %Y", "%Y %m", "%y %m", "%m%y", "%m%Y", "%Y%m", "%y%m"]

    try:
        if any(c.isalpha() for c in text):
            for key in month_dict.keys():
                text = text.lower().replace(key, month_dict[key])

        text = re.sub("[a-zA-Z,\\.\\-\\/'\\s]", " ", text)
        text = re.sub(" +", " ", text).strip()

        for f in format:
            try:
                text = datetime.strptime(text, f).strftime("01-%m-%Y %H:%M:%S")
                return text
            except Exception as err:
                # print(err)
                pass
        return ""

    except:
        return ""


def clean_product_name(text: str):
    """
    clean bbm product name
    """
    preffix = [
        "Nama Produk",
        "Jenis BBM",
        "Grade",
        "Product",
        "Produk",
    ]
    try:
        # if ":" in text:
        #     return text.split(":")[-1:][0].strip().upper()
        # else:
        #     for pre in preffix:
        #         try:
        #             text = text.lower()
        #             pre = pre.lower()
        #             text = text.replace(pre, "")
        #         except Exception as err:
        #             pass
        #     return text.strip()
        
        if ":" in text:
            return text.split(":")[-1:][0].strip()
        else:
            for pre in preffix:
                try:
                    text = text
                    pre = pre
                    text = text.replace(pre, "")
                except Exception as err:
                    pass
            return text.strip()
    except:
        return


def get_word_after_colon_or_remove_preffix(text: str, preffix: list):
    """
    example:
        preffix: ['alamat']
        text: alamat : jl. lorem ipsum
        out: jl. lorem ipsum
        text2: alamat jl.lorem ipsum
        out: jl.lorem ipsum
    """
    try:
        if ":" in text:
            return text.split(":")[-1:][0].strip().upper()
        else:
            for pre in preffix:
                try:
                    text = text.lower()
                    pre = pre.lower()
                    text = text.replace(pre, "")
                except Exception as err:
                    pass
            return text.upper().strip()
    except:
        return


def get_list_number(text):
    """
    get list of numbers
    """
    numbers = re.findall(r"\d+", text)
    numbers = [int(number) for number in numbers]
    return numbers


def get_time(text: str):
    """
    extract time from text
    """

    pattern = r"\b(?:\d{1,2}:\d{2}:\d{2}|\d{1,2}:\d{2})\b"
    time = re.findall(pattern, text)
    if time:
        return time[0]
    else:
        return "00:00:00"