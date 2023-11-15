import argparse
from enum import Enum
import io
import os

from google.cloud import vision
from google.cloud.vision import AnnotateImageResponse
from PIL import Image, ImageDraw

import re

import json

from flask import Flask
from flask_restful import Resource, Api, reqparse
import werkzeug

import base64

import time


from spellchecker import SpellChecker
 
spell = SpellChecker()
from datetime import datetime
# from dateutil import parser
# import pandas as pd
# import numpy as np
# import textdistance
# import re
# from collections import Counter

APPVersion = "2.0.0"
if "GOOGLE_APPLICATION_CREDENTIALS" not in os.environ:
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"]="config/key.json"

class ResultData:
    def __init__(self, tanggal, total, quantity, type = "", name = "", custname = "", custaddress = "", price = "", listTransaction = None, product = ""):
        self.transactiontype = "PLN" if type == "Prepaid" or type == "Postpaid" else "BBM" if type == "Bensin" else ""
        self.billingtype = type
        self.customerId = name
        self.custname = custname
        self.custaddress = custaddress
        self.rate = price
        self.quantity = quantity
        self.bill = total
        self.transactiondate = tanggal
        self.listTransaction = listTransaction
        self.product = product
    def __str__(self):
        return "Type: " + self.transactiontype + "BillingType: " + self.billingtype + "; Name: " + self.customerId + "; Custname: " + self.custname + "; Custaddress: " + self.custaddress + "; Price: " + self.rate + "; Quantity: " + self.quantity + "; Total: " + self.bill + "; tanggal: " + self.transactiondate
    def to_json(self):
        return json.dumps(self, default=lambda o: o.__dict__, sort_keys=True, indent=4)

class ReadMethod(Enum):
    InLine = 1
    LineBelow = 2
    Grid = 3
    
class FeatureType(Enum):
    PAGE = 1
    BLOCK = 2
    PARA = 3
    WORD = 4
    SYMBOL = 5

def draw_boxes_xy(image, minX, minY, maxX, maxY, color):
    """Draw a border around the image using the hints in the vector list."""
    draw = ImageDraw.Draw(image)

    draw.polygon(
        [
            minX,
            minY,
            maxX,
            minY,
            maxX,
            maxY,
            minX,
            maxY,
        ],
        None,
        color,
    )

    return image

def draw_boxes(image, bounds, color):
    """Draw a border around the image using the hints in the vector list."""
    draw = ImageDraw.Draw(image)

    for bound in bounds:
        draw.polygon(
            [
                bound.vertices[0].x,
                bound.vertices[0].y,
                bound.vertices[1].x,
                bound.vertices[1].y,
                bound.vertices[2].x,
                bound.vertices[2].y,
                bound.vertices[3].x,
                bound.vertices[3].y,
            ],
            None,
            color,
        )
    return image


def get_document_bounds(document, feature):
    bounds = []

    # Collect specified feature bounds by enumerating all document features
    for page in document.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    for symbol in word.symbols:
                        if feature == FeatureType.SYMBOL:
                            bounds.append(symbol.bounding_box)

                    if feature == FeatureType.WORD:
                        bounds.append(word.bounding_box)

                if feature == FeatureType.PARA:
                    bounds.append(paragraph.bounding_box)

            if feature == FeatureType.BLOCK:
                bounds.append(block.bounding_box)

    # The list `bounds` contains the coordinates of the bounding boxes.
    return bounds

def get_orientation(boundingBox):
    if boundingBox.vertices[0].x < boundingBox.vertices[1].x and boundingBox.vertices[0].y < boundingBox.vertices[3].y:
        return 0
    elif boundingBox.vertices[0].y < boundingBox.vertices[1].y and boundingBox.vertices[0].x > boundingBox.vertices[3].x:
        return 1
    elif boundingBox.vertices[0].x > boundingBox.vertices[1].x and boundingBox.vertices[0].y > boundingBox.vertices[3].y:
        return 2
    elif boundingBox.vertices[0].y > boundingBox.vertices[1].y and boundingBox.vertices[0].x < boundingBox.vertices[3].x:
        return 3
    else:
        return 0

def getMinX(boundingBox, orientation, width, height):
    if orientation == 0:
        return boundingBox.vertices[0].x
    elif orientation == 1:
        return boundingBox.vertices[0].y
    elif orientation == 2:
        return width - boundingBox.vertices[0].x
    elif orientation == 3:
        return height - boundingBox.vertices[0].y
    
def getMaxX(boundingBox, orientation, width, height):
    if orientation == 0:
        return boundingBox.vertices[2].x
    elif orientation == 1:
        return boundingBox.vertices[1].y
    elif orientation == 2:
        return width - boundingBox.vertices[1].x
    elif orientation == 3:
        return height - boundingBox.vertices[1].y

def getMinY(boundingBox, orientation, width, height):
    if orientation == 0:
        return boundingBox.vertices[0].y
    elif orientation == 1:
        return width - boundingBox.vertices[0].x
    elif orientation == 2:
        return height - boundingBox.vertices[0].y
    elif orientation == 3:
        return boundingBox.vertices[0].x

def getMaxY(boundingBox, orientation, width, height):
    if orientation == 0:
        return boundingBox.vertices[2].y
    elif orientation == 1:
        return width - boundingBox.vertices[2].x
    elif orientation == 2:
        return height - boundingBox.vertices[2].y
    elif orientation == 3:
        return boundingBox.vertices[2].x
    
def get_namePlat(sLine):
    tempLine = sLine

    insensitive_Plat = re.compile(re.escape('NO. PLAT'), re.IGNORECASE)
    tempLine = insensitive_Plat.sub('', tempLine)

    insensitive_Plat = re.compile(re.escape('VEHICLE NO'), re.IGNORECASE)
    tempLine = insensitive_Plat.sub('', tempLine)
    
    name = re.sub(r'[^\w]', '', tempLine)

    return name

def get_name(sLine):
    tempLine = sLine

    insensitive_produk = re.compile(re.escape('PRODUK'), re.IGNORECASE)
    tempLine = insensitive_produk.sub('', tempLine)
    insensitive_jenis_bbm = re.compile(re.escape('JENIS BBM'), re.IGNORECASE)
    tempLine = insensitive_jenis_bbm.sub('', tempLine)

    name = re.sub(r'[^\w]', '', tempLine)

    return name

def get_product_BBM(sLine):
    tempLine = sLine
    x = tempLine.find(":")
    if x == -1:
        insensitive_produk = re.compile(re.escape('PRODUK'), re.IGNORECASE)
        tempLine = insensitive_produk.sub('', tempLine)
        insensitive_jenis_bbm = re.compile(re.escape('JENIS BBM'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbm.sub('', tempLine)
        insensitive_jenis_bbmv2 = re.compile(re.escape('NAMA'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv2.sub('', tempLine)
        insensitive_jenis_bbmv3 = re.compile(re.escape('PRODUK'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv3.sub('', tempLine)
        insensitive_jenis_bbmv3 = re.compile(re.escape('GRADE'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv3.sub('', tempLine)
        
        product = re.sub(r'[^\w]', '', tempLine)
    else:
        misspelled = tempLine.split(":")
        tempLine = misspelled[1].strip()
        insensitive_produk = re.compile(re.escape('PRODUK'), re.IGNORECASE)
        tempLine = insensitive_produk.sub('', tempLine)
        insensitive_jenis_bbm = re.compile(re.escape('JENIS BBM'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbm.sub('', tempLine)
        insensitive_jenis_bbmv2 = re.compile(re.escape('NAMA'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv2.sub('', tempLine)
        insensitive_jenis_bbmv3 = re.compile(re.escape('PRODUK'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv3.sub('', tempLine)

        product = re.sub(r'[^\w]', '', tempLine)
    return product.upper()

def get_custname(sLine, textResult):
    tempLine = sLine

    escapeELA = re.compile(re.escape('ELA'), re.IGNORECASE)
    tempLine = escapeELA.sub('', tempLine)

    #escapeELE = re.compile(re.escape('ELE'), re.IGNORECASE)
    #tempLine = escapeELE.sub('', tempLine)

    #name = re.sub(r'[^\w]', '', tempLine)
    isFind = False
    
    for i in range(len(textResult)):
        tempString = textResult[i].replace(" ", "").upper()
        if(tempString.startswith(tempLine[0:2])):
            tempLine = textResult[i]
            isFind = True

    result = ""
    if isFind:
        result = tempLine
    else:
        result = tempLine.split(" ", 1)[0]
        
    return result

def get_address(sLine, textResult):
    tempLine = sLine

    insensitive_jenis_bbm = re.compile(re.escape('ELA'), re.IGNORECASE)
    tempLine = insensitive_jenis_bbm.sub('', tempLine)

    index = tempLine.find('Pascabayar/')
    if(index != -1):
        tempLine = tempLine[:index]

    #name = re.sub(r'[^\w]', '', tempLine)
    index = tempLine.find('No.')
    if(index != -1):
        tempLine = tempLine[:index] + ' ' + tempLine[index:]
        
    index = tempLine.find('RT.')
    if(index != -1):
        tempLine = tempLine[:index] + ' ' + tempLine[index:]

    index = tempLine.find('RW.')
    if(index != -1):
        tempLine = tempLine[:index] + ' ' + tempLine[index:]

    isFind = False
    
    for i in range(len(textResult)):
        tempString = textResult[i].replace(" ", "").upper()
        if(tempString.startswith(tempLine[0:2])):
            tempLine = textResult[i]
            isFind = True

    result = ""
    if isFind:
        result = tempLine
    else:
        result = tempLine.split(" ", 1)[0]
        
    return result


def get_price(sLine, trim = True):
    tempLine = sLine

    insensitive_harga = re.compile(re.escape('HARGA'), re.IGNORECASE)
    tempLine = insensitive_harga.sub('', tempLine)
    insensitive_liter = re.compile(re.escape('LITER'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    insensitive_rp = re.compile(re.escape('RP'), re.IGNORECASE)
    tempLine = insensitive_rp.sub('', tempLine)
    
    insensitive_rp = re.compile(re.escape('UNIT PRICE'), re.IGNORECASE)
    tempLine = insensitive_rp.sub('', tempLine)

    tempLine = tempLine.replace(" ", "")

    if trim:
        while(len(tempLine) > 0 and not tempLine[0].isdigit()):
            tempLine = tempLine[1:]
        
        while(len(tempLine) > 0 and not tempLine[len(tempLine) - 1].isdigit()):
            tempLine = tempLine[:len(tempLine) - 1]

    price = tempLine

    return price

def get_quantity(sLine):
    tempLine = sLine

    insensitive_liter = re.compile(re.escape('JML'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('LITER'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('L'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    insensitive_liter = re.compile(re.escape('VOLUME'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    tempLine = tempLine.replace(" ", "")

    while(len(tempLine) > 0 and not tempLine[0].isdigit()):
        tempLine = tempLine[1:]
    
    while(len(tempLine) > 0 and not tempLine[len(tempLine) - 1].isdigit()):
        tempLine = tempLine[:len(tempLine) - 1]

    quantity = tempLine

    # return quantity.strip().replace(".", "").replace(",", ".")
    return quantity.strip().replace(",", ".")

def get_total(sLine):
    tempLine = sLine

    insensitive_liter = re.compile(re.escape('JML'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('RUPIAH'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('RP'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    insensitive_liter = re.compile(re.escape('AMOUNT'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    tempLine = tempLine.replace(" ", "")

    while(len(tempLine) > 0 and not tempLine[0].isdigit()):
        tempLine = tempLine[1:]
    
    while(len(tempLine) > 0 and not tempLine[len(tempLine) - 1].isdigit()):
        tempLine = tempLine[:len(tempLine) - 1]

    total = tempLine

    return total.strip().replace(".", "").replace(",", "")

def isTanggal(sWord):
    data =  False
    if "JANUARI" in sWord or "JANUARY" in sWord:
        data = True
        return data
    if "FEBRUARI" in sWord or "FEBRUARY" in sWord:
        data = True
        return data
    if "MARET" in sWord or "MARCH" in sWord:
        data = True
        return data
    if "APRIL" in sWord or "APRIL" in sWord:
        data = True
        return data
    if "MEI" in sWord or "MAY" in sWord:
        data = True
        return data
    if "JUNI" in sWord or "JUNE" in sWord:
        data = True
        return data
    if "JULI" in sWord or "JULY" in sWord:
        data = True
        return data
    if "AGUSTUS" in sWord or "AUGUST" in sWord:
        data = True
        return data
    if "SEPTEMBER" in sWord:
        data = True
        return data
    if "OKTOBER" in sWord or "OCTOBER" in sWord:
        data = True
        return data
    if "NOVEMBER" in sWord or "NOPEMBER" in sWord:
        data = True
        return data
    if "DESEMBER" in sWord or "DECEMBER" in sWord:
        data = True
        return data
    else:
        data = False
        return data

def GetDate_Nokey(sWord, oldData):
    # sWord = "Kamis, 02 Desember 2022 08:42:42"
    sWord = sWord.upper().replace(" ", "")
    x = sWord.find(",")
    if x != -1:  
        sWord_S = sWord.split(",")
        sWord_data = sWord_S[1]
    else:
        sWord_data = sWord
        
    if "JANUARI" in sWord or "JANUARY" in sWord:
        data = sWord_data[9:13] + "-01-" + sWord_data[:2] + " " + sWord_data[13:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "FEBRUARI" in sWord or "FEBRUARY" in sWord:
        data = sWord_data[10:14] + "-02-" + sWord_data[:2] + " " + sWord_data[14:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "MARET" in sWord or "MARCH" in sWord:
        data = sWord_data[7:11] + "-03-" + sWord_data[:2] + " " + sWord_data[11:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "APRIL" in sWord:
        data = sWord_data[7:11] + "-04-" + sWord_data[:2] + " " + sWord_data[11:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "MEI" in sWord or "MAY" in sWord:
        data = sWord_data[5:9] + "-05-" + sWord_data[:2] + " " + sWord_data[9:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "JUNI" in sWord or "JUNE" in sWord:
        data = sWord_data[6:10] + "-06-" + sWord_data[:2] + " " + sWord_data[10:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "JULI" in sWord or "JULY" in sWord:
        data = sWord_data[6:10] + "-07-" + sWord_data[:2] + " " + sWord_data[10:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "AGUSTUS" in sWord or "AUGUST" in sWord:
        data = sWord_data[9:13] + "-08-" + sWord_data[:2] + " " + sWord_data[13:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "SEPTEMBER" in sWord:
        data = sWord_data[11:15] + "-09-" + sWord_data[:2] + " " + sWord_data[15:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "OKTOBER" in sWord or "OCTOBER" in sWord:
        data = sWord_data[9:13] + "-10-" + sWord_data[:2] + " " + sWord_data[13:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "NOVEMBER" in sWord or "NOPEMBER" in sWord:
        data = sWord_data[10:14] + "-11-" + sWord_data[:2] + " " + sWord_data[14:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "DESEMBER" in sWord or "DECEMBER" in sWord:
        data = sWord_data[10:14] + "-12-" + sWord_data[:2] + " " + sWord_data[14:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    else:
        return ""

def validate_date(date):
    try:
        res = False
        format = "%Y-%m-%d %H:%M:%S"
        res = bool(datetime.strptime(date, format))
        print("Does date match format? : " + str(res))
        return res
    except ValueError:
        return False
    # except Exception as e:
	#     res = False
    #     return res

def get_tanggal(sLine):
    tempLine = sLine

    insensitive_produk = re.compile(re.escape('TANGGAL'), re.IGNORECASE)
    tempLine = insensitive_produk.sub('', tempLine)

    tanggal = tempLine.strip()

    tanggal = tanggal[:10] + " " + tanggal[-8:]

    return tanggal

def get_tanggal_BBM(sLine):
    tempLine = sLine
    temptgl1 = ""
    temptgl2 = ""
    insensitive_produk = re.compile(re.escape('TANGGAL'), re.IGNORECASE)
    tempLine = insensitive_produk.sub('', tempLine)
    insensitive_tgl = re.compile(re.escape('WAKTU'), re.IGNORECASE)
    tempLine = insensitive_tgl.sub('', tempLine)
    insensitive_tgl = re.compile(re.escape('AKTU'), re.IGNORECASE)
    tempLine = insensitive_tgl.sub('', tempLine)
    tanggal = tempLine.strip()
    x = tanggal.find(":")
    if x == 0:
        tanggal = tanggal[x+1:len(tanggal)]
        tanggal = tanggal.strip()

    x_split = tanggal.split()
    xtanggal_len = len(x_split[0])
    if xtanggal_len == 8:
        match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
        res = datetime.strptime(match_str.group(), '%d/%m/%y').date()
    elif xtanggal_len == 10:
        match_str = re.search(r'\d{2}/\d{2}/\d{4}', x_split[0])
        res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
  
    tanggal = res.strftime('%Y-%m-%d')
    print("Computed date : " + tanggal)
    tempwaktu = x_split[1].replace(".", ":")
    #Get Waktu
    checktimevalid = isTimeFormat(tempwaktu)
    if checktimevalid == True:
        tanggal = tanggal + " " + tempwaktu
    
    # tanggal = tanggal[:10] + " " + tanggal[-8:]
    print("Computed date : " + tanggal)
    return tanggal

def get_waktu(sLine, tanggal):
    tempLine = sLine
    waktu = tempLine.strip()
    checktimevalid = isTimeFormat(waktu)
    if checktimevalid == True:
        waktu = tanggal + " " + waktu
    return waktu

def isTimeFormat(input):
    try:
        time.strptime(input, '%H:%M:%S')
        return True
    except ValueError:
        return False

def no_special_characters(s):
    pat=re.compile('[@_!#$%^&*()<>?/\|}{~:]')
    if pat.search(s):
        print(s + " has special characters")
        return True
    else:
        print(s + " has NO special characters")
        return False
        
def isVolume(input):
    temp_input = input
    x = input.find(":")
    if x != -1:
        misspelled = input.split(":")
        out =  False
        input = misspelled[0].strip()
        if input == "":
            input = misspelled[1].strip()
            if ("LITER" in input.upper() and "RP" not in input.upper() and "/" not in input.upper()) or "VOLUME" in input.upper() or "(L)" in input.upper():
                out = True
            else:
                out = False
        else:
            special_characters = no_special_characters(input)
            if special_characters == False:
                    if(re.match("^[a-zA-Z]*$", input) != None):
                        out = True
            if out == True:
                        input = spell.correction(input)
                        if input != None:
                            print(spell.correction(input))
                            print(spell.candidates(input))
                            if ("LITER" in input.upper() and "RP" not in input.upper() and "/" not in input.upper()) or "VOLUME" in input.upper() or "(L)" in input.upper():
                                out = True
                            else:
                                out = False
                        else:
                            out = False
    else:
        if ("LITER" in input.upper() and "RP" not in input.upper() and "/" not in input.upper()) or "VOLUME" in input.upper() or "(L)" in input.upper():
            out = True
        else:
            out = False
    return out

def get_word_array(line):
    lastX = 0
    sWords = []
    for word in line["words"]:
        if lastX == 0:
            sWord = ""
            for symbol in word["symbols"]:
                sWord = sWord + symbol.text
            sWords.append(sWord)
        else:
            if word["minX"] - lastX > 2 * (word["maxX"] - word["minX"]) / word["length"]:
                sWord = ""
                for symbol in word["symbols"]:
                    sWord = sWord + symbol.text
                sWords.append(sWord)
            else:
                sWord = ""
                for symbol in word["symbols"]:
                    sWord = sWord + symbol.text
                sWords[len(sWords) - 1] = sWords[len(sWords) - 1] + " " + sWord
        
        lastX = word["maxX"]
    return sWords

def GetDate(sWord):
    sWord = sWord.upper().replace(" ", "")
    if len(sWord) == 9:
        if "JAN" in sWord and not sWord.startswith("JAN"):
            return sWord[-4:] + "-01-" + sWord[:2] + " 00:00:00"
        if "FEB" in sWord and not sWord.startswith("FEB"):
            return sWord[-4:] + "-02-" + sWord[:2] + " 00:00:00"
        if "MAR" in sWord and not sWord.startswith("MAR"):
            return sWord[-4:] + "-03-" + sWord[:2] + " 00:00:00"
        if "APR" in sWord and not sWord.startswith("APR"):
            return sWord[-4:] + "-04-" + sWord[:2] + " 00:00:00"
        if "MEI" in sWord and not sWord.startswith("MEI"):
            return sWord[-4:] + "-05-" + sWord[:2] + " 00:00:00"
        if "JUN" in sWord and not sWord.startswith("JUN"):
            return sWord[-4:] + "-06-" + sWord[:2] + " 00:00:00"
        if "JUL" in sWord and not sWord.startswith("JUL"):
            return sWord[-4:] + "-07-" + sWord[:2] + " 00:00:00"
        if "AGU" in sWord and not sWord.startswith("AGU"):
            return sWord[-4:] + "-08-" + sWord[:2] + " 00:00:00"
        if "SEP" in sWord and not sWord.startswith("SEP"):
            return sWord[-4:] + "-09-" + sWord[:2] + " 00:00:00"
        if "OKT" in sWord and not sWord.startswith("OKT"):
            return sWord[-4:] + "-10-" + sWord[:2] + " 00:00:00"
        if "NOV" in sWord and not sWord.startswith("NOV"):
            return sWord[-4:] + "-11-" + sWord[:2] + " 00:00:00"
        if "DES" in sWord and not sWord.startswith("DES"):
            return sWord[-4:] + "-12-" + sWord[:2] + " 00:00:00"
        if sWord.startswith("APR"):
            return sWord[-4:] + "-04-01 00:00:00"
        if sWord.startswith("MAR"):
            return sWord[-4:] + "-03-01 00:00:00"
        else:
            return ""
    else:
        if sWord.startswith("JAN"):
            return sWord[-4:] + "-01-01 00:00:00"
        if sWord.startswith("FEB"):
            return sWord[-4:] + "-02-01 00:00:00"
        if sWord.startswith("MAR"):
            return sWord[-4:] + "-03-01 00:00:00"
        if sWord.startswith("APR"):
            return sWord[-4:] + "-04-01 00:00:00"
        if sWord.startswith("MEI"):
            return sWord[-4:] + "-05-01 00:00:00"
        if sWord.startswith("JUN"):
            return sWord[-4:] + "-06-01 00:00:00"
        if sWord.startswith("JUL"):
            return sWord[-4:] + "-07-01 00:00:00"
        if sWord.startswith("AGU"):
            return sWord[-4:] + "-08-01 00:00:00"
        if sWord.startswith("SEP"):
            return sWord[-4:] + "-09-01 00:00:00"
        if sWord.startswith("OKT"):
            return sWord[-4:] + "-10-01 00:00:00"
        if sWord.startswith("NOV"):
            return sWord[-4:] + "-11-01 00:00:00"
        if sWord.startswith("DES"):
            return sWord[-4:] + "-12-01 00:00:00"
        else:
            ""

def get_data(sLines, lines, textResult):
    type = ""
    name = ""
    price = ""
    quantity = ""
    total = ""
    tanggal = ""
    custname= ""
    custaddress = ""
    listTransaction = []
    product = ""

    lines.sort(key=lambda line: line["minY"])

    readMethod = ReadMethod.InLine
    for sLine in sLines:
        if "SPBU" in sLine.upper() or "PERTAMINA" in sLine.upper():
            type = "Bensin"
            readMethod = ReadMethod.InLine
            break
        elif "RIWAYAT" in sLine.upper().replace(" ", "") and "TOKEN" in sLine.upper().replace(" ", ""):
            type = "Prepaid"
            readMethod = ReadMethod.Grid
            break
        elif "ID" in sLine.upper().replace(" ", "") and "PELANGGAN" in sLine.upper().replace(" ", ""):
            type = "Postpaid"
            readMethod = ReadMethod.Grid
            break
        
        
    # Jika Metode Slines tidak terdeteksi maka akan memakai textResult    
    for tResult in textResult:
        if "SPBU" in tResult.upper() or "PERTAMINA" in tResult.upper() or "VIVO" in tResult.upper() or "SHELL" in tResult.upper():
            type = "Bensin"
            readMethod = ReadMethod.InLine
            break
        elif "PDAM" in tResult.upper() or "AIR" in tResult.upper():
            type = "PDAM_Pospaid"
            readMethod = ReadMethod.InLine
            break
        elif "RIWAYAT" in tResult.upper().replace(" ", "") and "TOKEN" in tResult.upper().replace(" ", ""):
            type = "Prepaid"
            readMethod = ReadMethod.Grid
            break
        elif "ID" in tResult.upper().replace(" ", "") and "PELANGGAN" in tResult.upper().replace(" ", ""):
            type = "Postpaid"
            readMethod = ReadMethod.Grid
            break
        
        
        # elif "RIWAYAT" in sLine.upper() and "PENGGUNAAN" in sLine.upper():
        #     type = "PLN Pascabayar"
        #     readMethod = ReadMethod.Grid
        #     break
        # elif "DAYA" in sLine.upper() or "TOKEN" in sLine.upper() or "KWH" in sLine.upper():
        #     type = "PLN Token"
        #     readMethod = ReadMethod.LineBelow
        #     break

    sWords = []
    field = ""
    if type == "Bensin": #Using textResult
        for i in range(len(textResult)):
            sLine = textResult[i]
            # sLine = sLine.replace(" ", "")
            if "PRODUK" in sLine.upper() or "JENIS BBM" in sLine.upper() or "NAMA PRODUK" in sLine.upper() or "GRADE" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    product = get_product_BBM(sLine)
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "HARGA/LITER" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    price = get_price(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "price"
            if isVolume(sLine.replace(" ", "")) == True:
                if('HARGA/LITER' not in sLine.upper()):
                    if readMethod == ReadMethod.InLine:
                        quantity = get_quantity(sLine)
                    elif readMethod == ReadMethod.LineBelow:
                        field = "quantity"
            if "RUPIAH" in sLine.upper() or "TOTAL HARGA" in sLine.upper() or "TOTAL" in sLine.upper() or "AMOUNT" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    total = get_total(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
            if "TANGGAL" in sLine.upper() or "WAKTU" in sLine.upper() or "AKTU" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    tanggal = get_tanggal_BBM(sLine)
                    len_tanggal = len(tanggal)
                    if len_tanggal == 10:
                        tanggal = get_waktu(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if isTanggal(sLine.upper())== True:
                if readMethod == ReadMethod.InLine:
                    tanggal = GetDate_Nokey(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if "PLAT" in sLine.upper() or "NO. PLAT" in sLine.upper() or "VEHICLE NO" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    name = get_namePlat(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "name"
                  
    elif type == "Prepaid" or type == "Postpaid":              
        for i in range(len(sLines)):
            sLine = sLines[i]

            if readMethod == ReadMethod.LineBelow and field:
                if field == "name":
                    name = get_name(sLine)
                    # custname = get_custname(sLines[i-2], textResult)
                elif field == "price":
                    price = get_price(sLine, False)
                elif field == "quantity":
                    quantity = get_quantity(sLine)
                elif field == "total":
                    total = get_total(sLine)
                elif field == "tanggal":
                    tanggal = get_tanggal(sLine)

                field = ""
                continue

            if readMethod == ReadMethod.Grid:
                line = lines[i]
                line["words"].sort(key=lambda word: word["minX"])
                sWord = ""
                lastMaxX = 0
                lastMinX = 0
                for word in line["words"]:
                    if lastMaxX == 0:
                        lastMaxX = word["maxX"]
                        lastMinX = word["minX"]
                        for symbol in word["symbols"]:
                            sWord = sWord + symbol.text
                    elif lastMaxX + ((lastMaxX - lastMinX) / len(sWord) if len(sWord) > 0 else 0) < word["minX"]:
                        sWords.append(sWord)
                        sWord = ""
                        for symbol in word["symbols"]:
                            sWord = sWord + symbol.text
                        lastMaxX = word["maxX"]
                        lastMinX = word["minX"]
                    else:
                        for symbol in word["symbols"]:
                            sWord = sWord + symbol.text
                        lastMaxX = word["maxX"]
                if sWord:
                    sWords.append(sWord)

    sTanggal = ""
    sTotal = ""
    sQuantity = ""

    tempSWord = ""

    if readMethod == ReadMethod.Grid:
        for index,sWord in enumerate(sWords):
            #print(sWord)
            if sWord.count('-') == 2:
                name = sWord
                #custumer name and address find by index before name
                #custname = get_custname(sWords[index-3])
                #custaddress = get_custname(sWords[index-1])
                for i in range(len(sLines)):
                    if(sLines[i-1].find('RW.')!= -1 or sLines[i-1].find('RT.')!= -1 or sLines[i-1].find('No.')!= -1):
                        if name in sLines[i]:
                            # print(get_word_array(lines[i-2]))
                            # print("get array customer name")
                            custname = get_custname(sLines[i-2],textResult)
                        if name in sLines[i]:
                            # print(get_word_array(lines[i]))
                            # print("get array customer address")
                            custaddress = get_address(sLines[i-1],textResult)
                    else:
                        isFind = False
                        indexFind = -1
                        for indexResult in range(len(textResult)):
                            if(textResult[indexResult].find('RW.')!= -1 or textResult[indexResult].find('No.')!= -1 or textResult[indexResult].find('RT.')!= -1 or textResult[indexResult].find('JL')!= -1):
                                isFind = True
                                indexFind = indexResult
                        if(isFind):
                            custaddress = textResult[indexFind]
                            custname = textResult[indexFind - 1]
                        else:
                            if name in sLines[i]:
                                #print(get_word_array(lines[i-2]))
                                #print("get array customer name");
                                custname = get_custname(sLines[i-2],textResult)
                            if name in sLines[i]:
                                #print(get_word_array(lines[i]))
                                #print("get array customer address");
                                custaddress = get_address(sLines[i-1],textResult)
                            
                                
            # if "-" in sWord:
            #     name = sWord
            elif "PRABAYAR" in sWord.upper() or "PASCABAYAR" in sWord.upper():
                tempProduct = sWord.upper().replace("PRABAYAR", "").replace("PASCABAYAR", "").replace("/", "").replace(" ", "")
                product = ""
                digitCounter = 0
                for i in range(len(tempProduct)):
                    if tempProduct[i].isdigit():
                        digitCounter = digitCounter + 1
                        if digitCounter > 1:
                            product = product + "/" + tempProduct[i:]
                            break
                        else:
                            product = product + tempProduct[i]
                    else:
                        product = product + tempProduct[i]

            elif type == "Prepaid":
                if not GetDate(sWord):
                    if "RP" in sWord.upper():
                        sTotal = sWord.upper().replace("RP", "").strip().replace(".", "").replace(",", "")
                    elif "KWH" in sWord.upper():
                        if sWord.upper().strip() == "KWH":
                            sQuantity = tempSWord.upper().strip().replace(",", ".")
                        else:
                            sQuantity = sWord.upper().replace("KWH", "").strip().replace(",", ".")
                        try:
                            sQuantity = float(sQuantity)
                        except:
                            print("Cannot convert " + sQuantity + " to float")
                else:
                    # print("sWord Tanggal: " + sWord)
                    sTanggal = GetDate(sWord)
                    
                if sTanggal and sTotal and sQuantity:
                    # print("Result: ")
                    # print(sTanggal)
                    # print(sTotal)
                    # print(sQuantity)
                    listTransaction.append(ResultData(sTanggal, sTotal, sQuantity))
                    sTanggal = ""
                    sTotal = ""
                    sQuantity = ""
            elif type == "Postpaid":
                ## print("sWord Tanggal: " + sWord)
                ##sTanggal = GetDate(sWord)
                
                ## print(sTanggal)
                if not GetDate(sWord):
                    if "RP" in sWord.upper():
                        sTotal = sWord.upper().replace("RP", "").strip().replace(".", "").replace(",", "")
                    elif sWord.upper().replace(".", "").replace(",", "").strip().isdigit():
                        sQuantity = sWord.upper().strip().replace(".", "").replace(",", ".")
                        try:
                            sQuantity = float(sQuantity)
                        except:
                            print("Cannot convert " + sQuantity + " to float")
                else:
                    sTanggal = GetDate(sWord)
                    sTotal = ""
                    sQuantity = ""
                    
                if sTanggal and sTotal and sQuantity:
                    listTransaction.append(ResultData(sTanggal, sTotal, sQuantity))
                    sTanggal = ""
                    sTotal = ""
                    sQuantity = ""

            tempSWord = sWord
    
    if type == "Bensin": #Using sLines
        for i in range(len(sLines)):
            sLine = sLines[i]
            # sLine = sLine.replace(" ", "")
            if "PRODUK" in sLine.upper() or "JENIS BBM" in sLine.upper() or "NAMA PRODUK" in sLine.upper() or "GRADE" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product == "":
                        product = get_product_BBM(sLine)
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "HARGA/LITER" in sLine.upper() or "UNIT PRICE" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if price == "":
                        price = get_price(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "price"
            if isVolume(sLine.replace(" ", "")) == True:
                if('HARGA/LITER' not in sLine.upper()):
                    if readMethod == ReadMethod.InLine:
                        if quantity == "":
                            quantity = get_quantity(sLine)
                    elif readMethod == ReadMethod.LineBelow:
                        field = "quantity"
            if "RUPIAH" in sLine.upper() or "TOTAL HARGA" in sLine.upper() or "TOTAL" in sLine.upper() or "AMOUNT" in sLine.upper(): 
                if readMethod == ReadMethod.InLine:
                    if total == "":
                        total = get_total(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
            if "TANGGAL" in sLine.upper() or "WAKTU" in sLine.upper() or "AKTU" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if tanggal == "":
                        tanggal = get_tanggal_BBM(sLine)
                        len_tanggal = len(tanggal)
                        if len_tanggal == 10:
                            tanggal = get_waktu(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if isTanggal(sLine.upper())== True:
                if readMethod == ReadMethod.InLine:
                    if tanggal == "":
                        tanggal = GetDate_Nokey(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if "PLAT" in sLine.upper() or "NO. PLAT" in sLine.upper() or "VEHICLE NO" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if name == "":
                        name = get_namePlat(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "name"
    
    result = ResultData(tanggal, total, quantity, type, name, custname, custaddress, price, listTransaction, product)

    return result

def read_text(image_file, document, fileout):
    symbols = []

    # width = 0
    # height = 0
    # orientation = 0

    for page in document.pages:
        # width = page.width
        # height = page.height
        for block in page.blocks:
            # orientation = get_orientation(block.bounding_box)
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    for symbol in word.symbols:
                        symbols.append(symbol)
    textResult = document.text.split('\n')
    #print(text)
    
    # bounds = []
    # for symbol in symbols:
    #     bounds.append(symbol.bounding_box)
    # draw_boxes(image_file, bounds, "green")

    words = []
    for symbol in symbols:
        word = filter(lambda word: word["minY"] <= symbol.bounding_box.vertices[2].y and word["maxY"] >= symbol.bounding_box.vertices[0].y and ((word["maxX"] + ((word["maxX"] - word["minX"]) / word["length"]) >= symbol.bounding_box.vertices[0].x and word["minX"] <= symbol.bounding_box.vertices[0].x) or (word["minX"] - ((word["maxX"] - word["minX"]) / word["length"]) <= symbol.bounding_box.vertices[2].x and word["maxX"] > symbol.bounding_box.vertices[2].x)), words)
        word = list(word)

        if len(word) == 0:
            word = {"minY": symbol.bounding_box.vertices[0].y, "maxY": symbol.bounding_box.vertices[2].y, "minX": symbol.bounding_box.vertices[0].x, "maxX": symbol.bounding_box.vertices[2].x, "length": 0, "symbols": []}
            words.append(word)
        else:
            word = word[0]
            if word["minY"] > symbol.bounding_box.vertices[0].y:
                word["minY"] = symbol.bounding_box.vertices[0].y
            if word["maxY"] < symbol.bounding_box.vertices[2].y:
                word["maxY"] = symbol.bounding_box.vertices[2].y
            if word["maxX"] < symbol.bounding_box.vertices[2].x:
                word["maxX"] = symbol.bounding_box.vertices[2].x
            if word["minX"] > symbol.bounding_box.vertices[0].x:
                word["minX"] = symbol.bounding_box.vertices[0].x

        word["length"] = word["length"] + len(symbol.text)
        word["symbols"].append(symbol)

    lines = []
    #print(words)
    #print("words cek ada space tidak")
    for word in words:
        line = filter(lambda line: line["minY"] + ((line["maxY"] - line["minY"]) / 2) <= word["maxY"] and line["maxY"] - ((line["maxY"] - line["minY"]) / 2) >= word["minY"], lines)
        line = list(line)

        if len(line) == 0:
            line = {"minY": word["minY"], "maxY": word["maxY"], "minX": word["minX"], "maxX": word["maxX"], "words": []}
            lines.append(line)
        else:
            line = line[0]
            if line["minY"] > word["minY"]:
                line["minY"] = word["minY"]
            if line["maxY"] < word["maxY"]:
                line["maxY"] = word["maxY"]
            if line["maxX"] < word["maxX"]:
                line["maxX"] = word["maxX"]
            if line["minX"] > word["minX"]:
                line["minX"] = word["minX"]
        
        line["words"].append(word)

    for line in lines:
        draw_boxes_xy(image_file, line["minX"], line["minY"], line["maxX"], line["maxY"], "green")


    
    sLines = []
    for line in lines:
        line["words"].sort(key=lambda word: word["minX"])
        sLine = ""
        for word in line["words"]:
            for symbol in word["symbols"]:
                sLine = sLine + symbol.text
            sLine = sLine + " "
        sLines.append(sLine)

    f = open(fileout,"w", encoding="utf-8")
    for sLine in sLines:
        f.write(sLine + "\n")
    f.close()

    result = get_data(sLines, lines, textResult)

    print(result)

    return result

    # for line in lines:
    #     line["symbols"].sort(key=lambda symbol: symbol.bounding_box.vertices[0].x)
    #     for symbol in line["symbols"]:
    #         print(symbol.text, end="")
    #     print()

    # print(len(document.pages))
    # print(len(document.pages[0].blocks))
    # print(document.pages[0].blocks[0].bounding_box)
    # print(len(document.pages[0].blocks[0].paragraphs))
    # print(document.pages[0].blocks[0].paragraphs[0].bounding_box)
    # print(len(document.pages[0].blocks[0].paragraphs[0].words))
    # print(document.pages[0].blocks[0].paragraphs[0].words[0].bounding_box)
    # print(len(document.pages[0].blocks[0].paragraphs[0].words[0].symbols))
    # print(document.pages[0].blocks[0].paragraphs[0].words[0].symbols[0].bounding_box)
    # print(document.pages[0].blocks[0].paragraphs[0].words[0].symbols[0].text)
    # print(document.pages[0].blocks[0].paragraphs[0].words[0].symbols[0].bounding_box)

def render_doc_text(filein, fileout, fileouttext):
    image_file = Image.open(filein)
    
    """Returns document bounds given an image."""
    client = vision.ImageAnnotatorClient()

    with io.open(filein, "rb") as filein:
        content = filein.read()

    image = vision.Image(content=content)

    response = client.text_detection(image=image)
    #print(response)
    document = response.full_text_annotation
    result = read_text(image_file, document, fileouttext)

    # bounds = get_document_bounds(document, FeatureType.BLOCK)
    # draw_boxes(image_file, bounds, "blue")
    # bounds = get_document_bounds(document, FeatureType.PARA)
    # draw_boxes(image_file, bounds, "red")
    # bounds = get_document_bounds(document, FeatureType.WORD)
    # draw_boxes(image_file, bounds, "yellow")

    if fileout != 0:
        image_file.save(fileout)
    else:
        image_file.show()

    return result

def extract_text(document):
    symbols = []

    for page in document.pages:
        # width = page.width
        # height = page.height
        for block in page.blocks:
            # orientation = get_orientation(block.bounding_box)
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    for symbol in word.symbols:
                        symbols.append(symbol)
    textResult = document.text.split('\n')

    words = []
    for symbol in symbols:
        word = filter(lambda word: word["minY"] <= symbol.bounding_box.vertices[2].y and word["maxY"] >= symbol.bounding_box.vertices[0].y and ((word["maxX"] + ((word["maxX"] - word["minX"]) / word["length"]) >= symbol.bounding_box.vertices[0].x and word["minX"] <= symbol.bounding_box.vertices[0].x) or (word["minX"] - ((word["maxX"] - word["minX"]) / word["length"]) <= symbol.bounding_box.vertices[2].x and word["maxX"] > symbol.bounding_box.vertices[2].x)), words)
        word = list(word)

        if len(word) == 0:
            word = {"minY": symbol.bounding_box.vertices[0].y, "maxY": symbol.bounding_box.vertices[2].y, "minX": symbol.bounding_box.vertices[0].x, "maxX": symbol.bounding_box.vertices[2].x, "length": 0, "symbols": []}
            words.append(word)
        else:
            word = word[0]
            if word["minY"] > symbol.bounding_box.vertices[0].y:
                word["minY"] = symbol.bounding_box.vertices[0].y
            if word["maxY"] < symbol.bounding_box.vertices[2].y:
                word["maxY"] = symbol.bounding_box.vertices[2].y
            if word["maxX"] < symbol.bounding_box.vertices[2].x:
                word["maxX"] = symbol.bounding_box.vertices[2].x
            if word["minX"] > symbol.bounding_box.vertices[0].x:
                word["minX"] = symbol.bounding_box.vertices[0].x

        word["length"] = word["length"] + len(symbol.text)
        word["symbols"].append(symbol)

    lines = []
    # print(words)
    # print("words cek ada space tidak")
    for word in words:
        line = filter(lambda line: line["minY"] + ((line["maxY"] - line["minY"]) / 2) <= word["maxY"] and line["maxY"] - ((line["maxY"] - line["minY"]) / 2) >= word["minY"], lines)
        line = list(line)

        if len(line) == 0:
            line = {"minY": word["minY"], "maxY": word["maxY"], "minX": word["minX"], "maxX": word["maxX"], "words": []}
            lines.append(line)
        else:
            line = line[0]
            if line["minY"] > word["minY"]:
                line["minY"] = word["minY"]
            if line["maxY"] < word["maxY"]:
                line["maxY"] = word["maxY"]
            if line["maxX"] < word["maxX"]:
                line["maxX"] = word["maxX"]
            if line["minX"] > word["minX"]:
                line["minX"] = word["minX"]
        
        line["words"].append(word)

    sLines = []
    for line in lines:
        line["words"].sort(key=lambda word: word["minX"])
        sLine = ""
        for word in line["words"]:
            for symbol in word["symbols"]:
                sLine = sLine + symbol.text
            sLine = sLine + " "
        sLines.append(sLine)

    fileout = "test.txt"
    f = open(fileout,"w", encoding="utf-8")
    for sLine in sLines:
        f.write(sLine + "\n")
    f.close()
    
    # print(sLines)
    # print("sLines")
    # print(lines)
    # print("lines")
    # print(textResult)
    # print("textResult")
    result = get_data(sLines, lines, textResult)

    # print(result)

    return result

class Vision(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()

    def get(self):
        msg = "Oke Kok"
        return msg, 200

    def post(self):
        self.parser.add_argument('name', type=str)
        self.parser.add_argument('image', type=str)
        
        args = self.parser.parse_args()
        
        filename = str(args.get("name"))
        image = str(args.get("image"))

        image = image.replace('data:image/jpeg;base64,', '')
        imageBytes = base64.b64decode(str(image))

        newFileByteArray = bytearray(imageBytes)
        
        if not os.path.isdir("uploads"):
            os.mkdir("uploads")
        f = open("uploads/" + filename,"wb+")
        f.write(newFileByteArray)
        f.close()

        result = render_doc_text("uploads/" + filename, filename, "test.txt")
        # result = "okay"

        # return result, 200
        return result.to_json(), 200

class VisionNew(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()

    def get(self):
        msg = "VisionAPI " + APPVersion
        return msg, 200
    
    def post(self):
        self.parser.add_argument('image', type=werkzeug.datastructures.FileStorage, location='files')
        
        args = self.parser.parse_args()
        
        image = args["image"]

        client = vision.ImageAnnotatorClient()

        image = vision.Image(content=image.read())

        response = client.text_detection(image=image)
        document = response.full_text_annotation

        result = extract_text(document)

        return result.to_json(), 200
