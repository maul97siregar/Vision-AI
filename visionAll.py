import argparse
from enum import Enum
import io
import os

from google.cloud import vision
from google.cloud.vision import AnnotateImageResponse
from PIL import Image, ImageDraw
import numpy as np

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
        # self.transactiontype = "PLN" if type == "Prepaid" or type == "Postpaid" else "BBM" if type == "Bensin" else ""
        self.transactiontype = "PLN" if type == "Prepaid" or type == "Postpaid" else "BBM" if type == "Bensin" else "WATER" if type == "PDAM_Postpaid" else ""
        # self.transactiontype = "PLN" if type == "Prepaid" or type == "Postpaid" else "WATER" if type == "PDAM_Postpaid" else ""
        self.billingtype = type
        self.customerId = name
        self.custname = custname
        self.custaddress = custaddress
        self.rate = price
        self.quantity = quantity
        self.bill = total
        self.transactiondate = tanggal.replace('/', '-')
        self.listTransaction = listTransaction
        self.product = product.replace("_", "").replace(":", "").replace("-","").replace("BIOSOLAR", "BIO SOLAR").replace("BioSolar", "BIO SOLAR").replace("PERTAMAXTURBO", "PERTAMAX TURBO").replace("PERTAMAXRACING", "PERTAMAX RACING").replace("PERTAMAXPLUS", "PERTAMAX PLUS").replace("PERTAMINADEX", "PERTAMINA DEX").replace("SHELLSUPER", "SHELL SUPER").replace("SHELLVPOWER", "SHELL V POWER").replace("SHELLSUPERRON92", "SHELL SUPER RON 92").replace("SHELLVPOWERRON95", "SHELL V POWER RON 95").replace("SHELLVPOWERDIESEL", "SHELL V POWER DIESEL").replace("SHELLDIESELEXTRA", "SHELL DIESEL EXTRA").replace("SHELLVPOWERNITRO+", "SHELL V POWER NITRO+").replace("REVVO92", "REVVO 92").replace("REVVO89", "REVVO 89").replace("REVVO95", "REVVO 95").replace("REVVO90", "REVVO 90").replace(":Revvo89", "REVVO 89").replace("BP90", "BP 90").replace("BP95", "BP 95").replace("BP92", "BP 92")
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
    print("NO PLAT")
    print(tempLine)
    insensitive_Plat = re.compile(re.escape('NO. PLAT'), re.IGNORECASE)
    tempLine = insensitive_Plat.sub('', tempLine)
    
    insensitive_Plat = re.compile(re.escape('NO PLAT'), re.IGNORECASE)
    tempLine = insensitive_Plat.sub('', tempLine)

    insensitive_Plat = re.compile(re.escape('VEHICLE NO'), re.IGNORECASE)
    tempLine = insensitive_Plat.sub('', tempLine)
    
    insensitive_Plat = re.compile(re.escape('NO. KEND.'), re.IGNORECASE)
    tempLine = insensitive_Plat.sub('', tempLine)
    
    name = re.sub(r'[^\w]', '', tempLine)    

    return name

# Add

def get_noPelanggan(sLine):
    tempLine = sLine

    insensitive_No_Pelanggan = re.compile(re.escape('NO PEL/SAMB'), re.IGNORECASE)
    tempLine = insensitive_No_Pelanggan.sub('', tempLine)

    insensitive_No_Pelanggan = re.compile(re.escape('NO. PELANGGAN'), re.IGNORECASE)
    tempLine = insensitive_No_Pelanggan.sub('', tempLine)
    
    insensitive_No_Pelanggan = re.compile(re.escape('NO PELANGGAN'), re.IGNORECASE)
    tempLine = insensitive_No_Pelanggan.sub('', tempLine)
    name = re.sub(r'[^\w]', '', tempLine)
    

    return name

def get_name_pdam(sLine):
    tempLine = sLine
    x = tempLine.find(":")
    if x == -1:    
        insentive_name_pdam = re.compile(re.escape('NAMA INSTANSI'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        insentive_name_pdam = re.compile(re.escape('NAMA PDAM'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        insentive_name_pdamv3 = re.compile(re.escape('MERCHANT PDAM'), re.IGNORECASE)
        tempLine = insentive_name_pdamv3.sub('', tempLine)
        
        insentive_name_pdam = re.compile(re.escape('PDAM'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        insensitive_produk = re.compile(re.escape('PRODUK'), re.IGNORECASE)
        tempLine = insensitive_produk.sub('', tempLine)
        
        name = re.sub(r'[^\w]', '', tempLine)
    
    else:
        misspelled = tempLine.split(":")
        tempLine = misspelled[1].strip()
        
        insentive_name_pdam = re.compile(re.escape('NAMA INSTANSI'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        insensitive_produk = re.compile(re.escape('PRODUK'), re.IGNORECASE)
        tempLine = insensitive_produk.sub('', tempLine)
        
        insentive_name_pdam = re.compile(re.escape('NAMA PDAM'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        insentive_name_pdam = re.compile(re.escape('MERCHANT PDAM'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        insentive_name_pdam = re.compile(re.escape('PDAM'), re.IGNORECASE)
        tempLine = insentive_name_pdam.sub('', tempLine)
        
        name = re.sub(r'[^\w]', '', tempLine)
            
    return name

def get_name_merchant(sLine):
    tempLine = sLine
    
    insentive_merchand = re.compile(re.escape('INDOMART'), re.IGNORECASE)
    tempLine = insentive_merchand.sub('', tempLine)
    
    insentive_merchandv2 = re.compile(re.escape('POS INDONESIA'), re.IGNORECASE)
    tempLine = insentive_merchandv2.sub('', tempLine)
    
    insentive_merchandv3 = re.compile(re.escape('ALFAMART'), re.IGNORECASE)
    tempLine = insentive_merchandv3.sub('', tempLine)
    
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
        insensitive_jenis_bbmv4 = re.compile(re.escape('Jenis BEN'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv4.sub('', tempLine)
        
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
        insensitive_jenis_bbmv4 = re.compile(re.escape('Jenis BEN'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv4.sub('', tempLine)
        insensitive_jenis_bbmv3 = re.compile(re.escape('GRADE'), re.IGNORECASE)
        tempLine = insensitive_jenis_bbmv3.sub('', tempLine)

        product = re.sub(r'[^\w]', '', tempLine)
    # print("Get produk bbm")
    return product.upper()


def get_product_BBM_V2(sLine):
    tempLine = sLine
    insensitive_product = re.compile(re.escape('PRODUCT'), re.IGNORECASE)
    tempLine = insensitive_product.sub('', tempLine)
    insensitive_grade = re.compile(re.escape('GRADE'), re.IGNORECASE)
    tempLine = insensitive_grade.sub('', tempLine)

    product = re.sub(r'[^\w]', '', tempLine)
    return product

def get_product_BBM_V3(sLine):
    tempLine = sLine

    insensitive_liter = re.compile(re.escape('PRODUCT'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('GRADE'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    insensitive_grade = re.compile(re.escape('JENIS BBM'), re.IGNORECASE)
    tempLine = insensitive_grade.sub('', tempLine)
    
    #tempLine = tempLine.replace(" ", "")

    product = tempLine.strip().replace(" ", "").replace("JenisBBM:SOLAR", "SOLAR")
    return product

def get_custname(sLine, textResult):
    tempLine = sLine

    escapeELA = re.compile(re.escape('ELA'), re.IGNORECASE)
    tempLine = escapeELA.sub('', tempLine)

    escapeELA = re.compile(re.escape('NAMA'), re.IGNORECASE)
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
    
    # add
    insentitive_bayar = re.compile(re.escape('BAYAR'), re.IGNORECASE)
    tempLine = insentitive_bayar.sub('', tempLine)
    insentitive_total = re.compile(re.escape('TOTAL'), re.IGNORECASE)
    tempLine = insentitive_total.sub('', tempLine)
    
    insensitive_rp = re.compile(re.escape('UNIT PRICE'), re.IGNORECASE)
    tempLine = insensitive_rp.sub('', tempLine)

    insensitive_total = re.compile(re.escape('JML'), re.IGNORECASE)
    tempLine = insensitive_total.sub('', tempLine)

    insensitive_total = re.compile(re.escape('RUPIAH'), re.IGNORECASE)
    tempLine = insensitive_total.sub('', tempLine)

    insensitive_total = re.compile(re.escape('RP'), re.IGNORECASE)
    tempLine = insensitive_total.sub('', tempLine)
    
    insensitive_total = re.compile(re.escape('AMOUNT'), re.IGNORECASE)
    tempLine = insensitive_total.sub('', tempLine)
    
    insensitive_total = re.compile(re.escape('TOTAL TAGIHAN'), re.IGNORECASE)
    tempLine = insensitive_total.sub('', tempLine)
    tempLine = tempLine.replace(" ", "")

    if trim:
        while(len(tempLine) > 0 and not tempLine[0].isdigit()):
            tempLine = tempLine[1:]
        
        while(len(tempLine) > 0 and not tempLine[len(tempLine) - 1].isdigit()):
            tempLine = tempLine[:len(tempLine) - 1]

    price = tempLine

    return price

def get_quantity(sLine):
    # print("get_quantity " + sLine)
    tempLine = sLine

    insensitive_liter = re.compile(re.escape('JML'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('LITER'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('L'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    insensitive_liter = re.compile(re.escape('VOLUME'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    insensitive_kubik = re.compile(re.escape('M3'), re.IGNORECASE)
    tempLine = insensitive_kubik.sub('', tempLine)
    
    insensitive_kubik = re.compile(re.escape('JML LITER'), re.IGNORECASE)
    tempLine = insensitive_kubik.sub('', tempLine)
    
    insensitive_kubik = re.compile(re.escape('(L)'), re.IGNORECASE)
    tempLine = insensitive_kubik.sub('', tempLine)
    
    tempLine = tempLine.replace(" ", "")
    tempLine = tempLine.replace(",", ".")

    while(len(tempLine) > 0 and not tempLine[0].isdigit()):
        tempLine = tempLine[1:]
    
    while(len(tempLine) > 0 and not tempLine[len(tempLine) - 1].isdigit()):
        tempLine = tempLine[:len(tempLine) - 1]

    quantity = tempLine

    return quantity.replace(",", ".")

def get_total(sLine, trim = True):
    tempLine = sLine

    insensitive_liter = re.compile(re.escape('JML'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('RUPIAH'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)

    insensitive_liter = re.compile(re.escape('RP'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    insensitive_liter = re.compile(re.escape('AMOUNT'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    insensitive_liter = re.compile(re.escape('TOTAL HARGA'), re.IGNORECASE)
    tempLine = insensitive_liter.sub('', tempLine)
    
    tempLine = tempLine.replace(" ", "")
        
    if trim:
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
def GetDate_Nokey_V3(sWord, oldData):
    # sWord = "Kamis, 02 Desember 2022 08:42:42"
    sWord = sWord.upper().replace(" ", "")
    print("Nokey 1")
    print(sWord)
    x = sWord.find(",")
    if x != -1:  
        sWord_S = sWord.split(",")
        sWord_data = sWord_S[1]
    else:
        sWord_data = sWord
        
    # sWord_dataLen = len(sWord_data)
    if "JANUARI" in sWord or "JANUARY" in sWord:
        data = sWord_data[:2] + "-01-" + sWord_data[9:13]  + " " + sWord_data[13:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "FEBRUARI" in sWord or "FEBRUARY" in sWord:
        data = sWord_data[:2] + "-02-" + sWord_data[10:14] + " " + sWord_data[14:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "MARET" in sWord or "MARCH" in sWord:
        data =  sWord_data[:2] + "-03-" + sWord_data[7:11] + " " + sWord_data[11:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "APRIL" in sWord:
        data = sWord_data[:2] + "-04-" + sWord_data[7:11] + " " + sWord_data[11:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "MEI" in sWord or "MAY" in sWord:
        data = sWord_data[:2] + "-05-" + sWord_data[5:9] + " " + sWord_data[9:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "JUNI" in sWord or "JUNE" in sWord:
        data = sWord_data[:2] + "-06-" + sWord_data[6:10] + " " + sWord_data[10:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "JULI" in sWord or "JULY" in sWord:
        data = sWord_data[:2] + "-07-" + sWord_data[6:10] + " " + sWord_data[10:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "AGUSTUS" in sWord or "AUGUST" in sWord:
        data = sWord_data[:2] + "-08-" + sWord_data[9:13] + " " + sWord_data[13:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "SEPTEMBER" in sWord:
        data = sWord_data[:2] + "-09-" + sWord_data[11:15] + " " + sWord_data[15:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "OKTOBER" in sWord or "OCTOBER" in sWord:
        data = sWord_data[:2] + "-10-" + sWord_data[9:13] + " " + sWord_data[13:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "NOVEMBER" in sWord or "NOPEMBER" in sWord:
        data = sWord_data[:2]  + "-11-" + sWord_data[10:14] + " " + sWord_data[14:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "DESEMBER" in sWord or "DECEMBER" in sWord:
        data = sWord_data[:2] + "-12-" + sWord_data[10:14] + " " + sWord_data[14:]
        isDate = validate_date(data)
        if isDate == True:
            return data
        else:
           return oldData
    else:
        return ""

def GetDate_Nokey(sWord, oldData):
    # sWord = "Kamis, 02 Desember 2022 08:42:42"
    sWord = sWord.upper().replace(" ", "")
    x = sWord.find(",")
    if x != -1:  
        sWord_S = sWord.split(",")
        sWord_data = sWord_S[1]
    else:
        sWord_data = sWord
        
    # sWord_dataLen = len(sWord_data)
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
    
def GetDate_Nokey_V2(sWord, oldData):
    sWord = sWord.upper().replace(" ", "")
    x = sWord.find(",")
    if x != -1:  
        sWord_S = sWord.split(",")
        sWord_data = sWord_S[1]
    else:
        sWord_data = sWord
        
    # sWord_dataLen = len(sWord_data)
    if "JANUARI" in sWord or "JANUARY" in sWord:
        data = sWord_data[9:13] + "-01-" + sWord_data[:2] + " " + sWord_data[13:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "FEBRUARI" in sWord or "FEBRUARY" in sWord:
        data = sWord_data[10:14] + "-02-" + sWord_data[:2] + " " + sWord_data[14:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "MARET" in sWord or "MARCH" in sWord:
        data = sWord_data[7:11] + "-03-" + sWord_data[:2] + " " + sWord_data[11:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "APRIL" in sWord:
        data = sWord_data[7:11] + "-04-" + sWord_data[:2] + " " + sWord_data[11:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "MEI" in sWord or "MAY" in sWord:
        data = sWord_data[5:9] + "-05-" + sWord_data[:2] + " " + sWord_data[9:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "JUNI" in sWord or "JUNE" in sWord:
        data = sWord_data[6:10] + "-06-" + sWord_data[:2] + " " + sWord_data[10:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "JULI" in sWord or "JULY" in sWord:
        data = sWord_data[6:10] + "-07-" + sWord_data[:2] + " " + sWord_data[10:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "AGUSTUS" in sWord or "AUGUST" in sWord:
        data = sWord_data[9:13] + "-08-" + sWord_data[:2] + " " + sWord_data[13:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "SEPTEMBER" in sWord:
        data = sWord_data[11:15] + "-09-" + sWord_data[:2] + " " + sWord_data[15:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "OKTOBER" in sWord or "OCTOBER" in sWord:
        data = sWord_data[9:13] + "-10-" + sWord_data[:2] + " " + sWord_data[13:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "NOVEMBER" in sWord or "NOPEMBER" in sWord:
        data = sWord_data[10:14] + "-11-" + sWord_data[:2] + " " + sWord_data[14:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    if "DESEMBER" in sWord or "DECEMBER" in sWord:
        data = sWord_data[10:14] + "-12-" + sWord_data[:2] + " " + sWord_data[14:]
        isDate = validate_date_v2(data)
        if isDate == True:
            return data
        else:
           return oldData
    else:
        return ""

def validate_date(date):
    try:
        res = False
        format = "%d-%m-%Y %H:%M:%S"
        res = bool(datetime.strptime(date, format))
        return res
    except ValueError:
        return False
    # except Exception as e:
	#     res = False
    #     return res
    
def validate_date_v2(date):
    try:
        res = False
        format = "%Y-%m-%d %H:%M:%S"
        res = bool(datetime.strptime(date, format))
        return res
    except ValueError:
        return False

def validate_date_v3(date):
    try:
        res = False
        format = "%d/%m/%Y %H:%M:%S"
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
    # tempLine.replace("f").replace("fi", "").replace(" fi", "")
    temptgl1 = ""
    temptgl2 = ""
    tempwaktu = ""
    insensitive_produk = re.compile(re.escape('TANGGAL'), re.IGNORECASE)
    tempLine = insensitive_produk.sub('', tempLine)
    insensitive_tgl = re.compile(re.escape('WAKTU'), re.IGNORECASE)
    tempLine = insensitive_tgl.sub('', tempLine)
    insensitive_tgl = re.compile(re.escape('AKTU'), re.IGNORECASE)
    tempLine = insensitive_tgl.sub('', tempLine)
    insensitive_sun = re.compile(re.escape('SUN'), re.IGNORECASE)
    tempLine = insensitive_sun.sub('', tempLine)
    insensitive_mon = re.compile(re.escape('MON'), re.IGNORECASE)
    tempLine = insensitive_mon.sub('', tempLine)
    insensitive_tue = re.compile(re.escape('TUE'), re.IGNORECASE)
    tempLine = insensitive_tue.sub('', tempLine)
    insensitive_wed = re.compile(re.escape('WED'), re.IGNORECASE)
    tempLine = insensitive_wed.sub('', tempLine)
    insensitive_thu = re.compile(re.escape('THU'), re.IGNORECASE)
    tempLine = insensitive_thu.sub('', tempLine)
    insensitive_fri = re.compile(re.escape('FRI'), re.IGNORECASE)
    tempLine = insensitive_fri.sub('', tempLine)
    insensitive_sat = re.compile(re.escape('SAT'), re.IGNORECASE)
    tempLine = insensitive_sat.sub('', tempLine)

    tanggal = tempLine.strip()
    x = tanggal.find(":")
    if x == 0:
        tanggal = tanggal[x+1:len(tanggal)]
        tanggal = tanggal.strip()

    x_split = tanggal.split()
    xtanggal_len = len(x_split[0])
    longArray = len(x_split)
    formatTanggal = x_split[0]

    #Format YYYY/MM/DD
    if (re.search(r'\d{4}/\d{2}/\d{2}', formatTanggal)) :
        print("MASUK METODE di GET BBM YYYY/MM/DD")
        if xtanggal_len == 8:
            match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
        elif xtanggal_len == 9:
            match_str = re.search(r'\d{4}/\d{1}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
        elif xtanggal_len == 10:
            match_str = re.search(r'\d{4}/\d{2}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
            
    if (re.search(r'\d{2}/\d{2}/\d{4}', formatTanggal)) :
        print("MASUK METODE DD/MM/YYY", tempLine)
        if xtanggal_len == 8:
            match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
        elif xtanggal_len == 9:
            match_str = re.search(r'\d{2}/\d{1}/\d{4}', x_split[0])
            res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
        elif xtanggal_len == 10:
            match_str = re.search(r'\d{2}/\d{2}/\d{4}', x_split[0])
            res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
    
    # if xtanggal_len == 9:
    #     match_str = re.search(r'\d{2}/\d{1}/\d{4}', x_split[0])
    #     res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
        
    #     tanggal = res.strftime('%d-%m-%Y')
    #     if longArray > 1 :
    #         tempwaktu = x_split[1].replace(".", ":")
    #     checktimevalid = isTimeFormatV2(tempwaktu)
    #     if checktimevalid == True:
    #         tanggal = tanggal[:10] + " " + tempwaktu
    #     return tanggal
        
    # if xtanggal_len == 8:
    #     match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
    #     res = datetime.strptime(match_str.group(), '%d/%m/%y').date()
    # elif xtanggal_len == 10:
    #     match_str = re.search(r'\d{2}/\d{2}/\d{4}', x_split[0])
    #     res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
  
    tanggal = res.strftime('%d-%m-%Y')
    print("Computed date : " + tanggal)
    if longArray > 1 :
        tempwaktu = x_split[1].replace(".", ":")
    checktimevalid = isTimeFormat(tempwaktu)
    if checktimevalid == True:
        tanggal = tanggal + " " + tempwaktu
    print("Computed date : " + tanggal)
    
    tanggal = re.sub(r'[a-zA-Z]', '', tanggal)    
    return tanggal

def get_waktu(sLine, tanggal):
    tempLine = sLine
    waktu = tempLine.strip()
    
    lenghtWaktu = len(waktu)
    x_split = waktu.split()

    #if date and time no space (20-01-0112:12:23)
    if lenghtWaktu == 18 and not re.search(r'\d{2}/\d{1}/\d{4}', tanggal):
        splitLength = [x_split[0][i:i+10] for i in range(0, len(x_split[0]), 10)]
        waktu = splitLength[0] + " " + splitLength[1]
    
    checktimevalid = isTimeFormatV2(waktu)
    if checktimevalid == True:
        waktu = tanggal + " " + waktu
    else:
        checktimevalid = isTimeFormatV2(waktu)
        if checktimevalid == True:
            waktu = tanggal + " " + waktu
            
    waktu = re.sub(r'[a-zA-Z]', '', waktu)    
    return waktu

def get_waktuV2(sLine, tanggal):
    tempLine = sLine
    waktu = tempLine.strip()
    date_split = tempLine.split(" ")
    checktimevalid = isTimeFormatV2(date_split[1])
    if checktimevalid == True:
        waktu = tanggal + " " + date_split[1]
    else:
        checktimevalid = isTimeFormatV2(date_split[1])
        if checktimevalid == True:
            waktu = tanggal + " " + date_split[1]
    return waktu

def isTimeFormat(input):
    try:
        time.strptime(input, '%H:%M:%S')
        return True
    except ValueError:
        return False
def isTimeFormatV2(input):
    try:
        time.strptime(input, '%H:%M')
        return True
    except ValueError:
        return False
    
def get_tanggal_BBM_V2(sLine):
    tempLine = sLine
    temptgl1 = ""
    temptgl2 = ""
    insensitive_produk = re.compile(re.escape('DATE'), re.IGNORECASE)
    tempLine = insensitive_produk.sub('', tempLine)
    tanggal = tempLine.strip()
    x = tanggal.find(":")
    if x == 0:
        tanggal = tanggal[x+1:len(tanggal)]
        tanggal = tanggal.strip()

    x_split = tanggal.split()
    xtanggal_len = len(x_split[0])
    if xtanggal_len == 8:
        match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
        res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
    elif xtanggal_len == 10:
        match_str = re.search(r'\d{4}/\d{2}/\d{2}', x_split[0])
        res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
  
    tanggal = res.strftime('%d-%m-%Y')
    print("Computed date : " + tanggal)
    tempwaktu = x_split[1].replace(".", ":")
    #Get Waktu
    checktimevalid = isTimeFormatV2(tempwaktu)
    if checktimevalid == True:
        tanggal = tanggal + " " + tempwaktu
    
    # tanggal = tanggal[:10] + " " + tanggal[-8:]
    print("Computed date get_tanggal_BBM_V2 : " + tanggal)
    return tanggal

def get_tanggal_BBM_V3(sLine):
    tempLine = sLine.replace("-", "/")
    
    tempLine = re.sub(r'[a-zA-Z]', '', tempLine)    
    print("SLINEEEE : ", tempLine)

    # tempLine.replace("f").replace("fi", "").replace(" fi", "")
    # .replace("-","/").replace(" fi", "")
    temptgl1 = ""
    temptgl2 = ""
    insensitive_produk = re.compile(re.escape('DATE'), re.IGNORECASE)
    tempLine = insensitive_produk.sub('', tempLine)
    tanggal = tempLine.strip()
    x = tanggal.find(":")
    if x == 0:
        tanggal = tanggal[x+1:len(tanggal)]
        tanggal = tanggal.strip()

    x_split = tanggal.split()
    
    getCount = len(x_split)
    print("TANGGAL : ", x_split)

    formatTanggal = x_split[0]
    xtanggal_len = len(x_split[0])
    
    if xtanggal_len > 10 :
            splitLength = [x_split[0][i:i+10] for i in range(0, len(x_split[0]), 10)]
            formatTanggal = splitLength[0]
            xtanggal_len = len(splitLength[0])
    
    #example format 10-10-2023
    if (re.search(r'\d{2}/\d{2}/\d{4}', formatTanggal)) :
        print("MASUK METODE SATU")
        if xtanggal_len == 8:
            match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
        elif xtanggal_len == 9:
            match_str = re.search(r'\d{2}/\d{1}/\d{4}', x_split[0])
            res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
        elif xtanggal_len == 10:
            match_str = re.search(r'\d{2}/\d{2}/\d{4}', x_split[0])
            print(match_str)
            res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()

    #example format 2023-10-10
    if (re.search(r'\d{4}/\d{2}/\d{2}', formatTanggal)) :
        print("MASUK METODE 2")
        if xtanggal_len == 8:
            match_str = re.search(r'\d{2}/\d{2}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
        elif xtanggal_len == 9:
            match_str = re.search(r'\d{4}/\d{1}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
        elif xtanggal_len == 10:
            match_str = re.search(r'\d{4}/\d{2}/\d{2}', x_split[0])
            res = datetime.strptime(match_str.group(), '%Y/%m/%d').date()
  
    tanggal = res.strftime('%d-%m-%Y')
    print("Computed date : " + tanggal)
    tempwaktu = x_split[1].replace(".", ":")
    #Get Waktu
    checktimevalid = isTimeFormatV2(tempwaktu)
    if checktimevalid == True:
        tanggal = tanggal + " " + tempwaktu
    
    # tanggal = tanggal[:10] + " " + tanggal[-8:]
    print("Computed date get_tanggal_BBM_V3 : " + tanggal)
    return tanggal

def getTanggalShell(sLine):
    tempLine = sLine
    insensitive_sun = re.compile(re.escape('SUN'), re.IGNORECASE)
    tempLine = insensitive_sun.sub('', tempLine)
    insensitive_mon = re.compile(re.escape('MON'), re.IGNORECASE)
    tempLine = insensitive_mon.sub('', tempLine)
    insensitive_tue = re.compile(re.escape('TUE'), re.IGNORECASE)
    tempLine = insensitive_tue.sub('', tempLine)
    insensitive_wed = re.compile(re.escape('WED'), re.IGNORECASE)
    tempLine = insensitive_wed.sub('', tempLine)
    insensitive_thu = re.compile(re.escape('THU'), re.IGNORECASE)
    tempLine = insensitive_thu.sub('', tempLine)
    insensitive_fri = re.compile(re.escape('FRI'), re.IGNORECASE)
    tempLine = insensitive_fri.sub('', tempLine)
    insensitive_sat = re.compile(re.escape('SAT'), re.IGNORECASE)
    tempLine = insensitive_sat.sub('', tempLine)
    tanggal = tempLine.strip()
    x = tanggal.find(":")
    if x == 0:
        tanggal = tanggal[x+1:len(tanggal)]
        tanggal = tanggal.strip()

    x_split = tanggal.split()
    xtanggal_len = len(x_split[0])
    if xtanggal_len == 9:
        match_str = re.search(r'\d{2}/\d{1}/\d{4}', x_split[0])
        res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
        
        tanggal = res.strftime('%d-%m-%Y')
        tempwaktu = x_split[1].replace(".", ":")
        #Get Waktu
        checktimevalid = isTimeFormatV2(tempwaktu)
        if checktimevalid == True:
            tanggal = tanggal + " " + tempwaktu
        return tanggal
        
    if xtanggal_len == 10:
        match_str = re.search(r'\d{2}/\d{2}/\d{4}', x_split[0])
        res = datetime.strptime(match_str.group(), '%d/%m/%Y').date()
  
        tanggal = res.strftime('%d-%m-%Y')
        tempwaktu = x_split[1].replace(".", ":")
        checktimevalid = isTimeFormatV2(tempwaktu)
        if checktimevalid == True:
            tanggal = tanggal + " " + tempwaktu
    
    # tanggal = tanggal[:10] + " " + tanggal[-8:]
    return tanggal

def getTanggalBBMV3(sLine):
    tempLine = sLine
    insensitive_sun = re.compile(re.escape('SENIN'), re.IGNORECASE)
    tempLine = insensitive_sun.sub('', tempLine)
    insensitive_mon = re.compile(re.escape('SELASA'), re.IGNORECASE)
    tempLine = insensitive_mon.sub('', tempLine)
    insensitive_tue = re.compile(re.escape('RABU'), re.IGNORECASE)
    tempLine = insensitive_tue.sub('', tempLine)
    insensitive_wed = re.compile(re.escape('KAMIS'), re.IGNORECASE)
    tempLine = insensitive_wed.sub('', tempLine)
    insensitive_thu = re.compile(re.escape('JUMAT'), re.IGNORECASE)
    tempLine = insensitive_thu.sub('', tempLine)
    insensitive_thu = re.compile(re.escape("JUM'AT"), re.IGNORECASE)
    tempLine = insensitive_thu.sub('', tempLine)
    insensitive_fri = re.compile(re.escape('SABTU'), re.IGNORECASE)
    tempLine = insensitive_fri.sub('', tempLine)
    insensitive_sat = re.compile(re.escape('MINGGU'), re.IGNORECASE)
    tempLine = insensitive_sat.sub('', tempLine)
    tanggal = tempLine.strip()
    print("Tanggal V 3 : ")
    print(tanggal)
    if isTanggal(tanggal.upper()) == True:
        print("Tanggal V Masuk IF : ")
        tanggal = GetDate_Nokey_V3(tanggal, tanggal)
        print("Tanggal V 3_1 : ")
        print(tanggal)
    return tanggal

def validate_shell_date(date):
    try:
        format = "%d-%m-%Y"
        convBool = str(date)
        res = datetime.strptime(convBool, format).date()
        tanggal = res.strftime('%d-%m-%Y %H:%M')

        print("Compute Date  validate_shell_date: " + tanggal)
        
        return tanggal
    except ValueError:
        return False 

def validate_nokey_v3(date):
    try:
        format = "%d/%m/%Y"
        convBool = str(date)
        res = datetime.strptime(convBool, format).date()
        print("Compute Date validate_nokey_v3 : ")
        print(res)
        tanggal = res.strftime('%d-%m-%Y %H:%M')

        print("Convert : " + tanggal)
        
        return tanggal
    except ValueError:
        return False
    
def validate_datetime(datetime_str):
    try:
        format_str = "%d/%m/%Y"
        date_split = datetime_str.split(" ")
        datetime.strptime(date_split[0], format_str)
        return True
    except ValueError:
        return False
        
def validate_date_v5(date):
    try:
        format = "%d/%m/%Y %H:%M"
        convBool = str(date)
        res = datetime.strptime(convBool, format).date()
        tanggal = res.strftime('%d-%m-%Y %H:%M')
        
        return tanggal
        
    except ValueError:
        return False
    
def get_waktu_V2(sLine, tanggal):
    tempLine = sLine
    waktu = tempLine.strip()
    checktimevalid = isTimeFormatV2(waktu)
    if checktimevalid == True:
        waktu = tanggal + " " + waktu
    return waktu

def isTimeFormatV2(input):
    try:
        time.strptime(input, '%H:%M')
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
            if ("LITER" in input.upper() and "RP" not in input.upper() and "/" not in input.upper()) or "VOLUME" in input.upper() or "(L)" in input.upper() or "JML LITER" in input.upper():
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
                            if ("LITER" in input.upper() and "RP" not in input.upper() and "/" not in input.upper()) or "VOLUME" in input.upper() or "(L)" in input.upper() or "JML LITER" in input.upper():
                                out = True
                            else:
                                out = False
                        else:
                            out = False
    else:
        if ("LITER" in input.upper() and "RP" not in input.upper() and "/" not in input.upper()) or "VOLUME" in input.upper() or "(L)" in input.upper() or "JML LITER" in input.upper():
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
    # print("TANGGAL WOI : ", sWord)
    sWord = sWord.upper().replace(" ", "").replace("AGUS", "AGUSTUS2023")
    
    if re.findall(r'[.,]', sWord) :
        sWord = re.sub(r'[,.+@#$%^&*+=|]', '', sWord)
        # print("NAAAH NEMU KAN : ", re.sub(r'[,.+@#$%^&*+=|]', '', sWord))
        
    
    ##Existing
    # if len(sWord) == 9:
    #         if "JAN" in sWord and not sWord.startswith("JAN"):
    #             return sWord[-4:] + "-01-" + sWord[:2] + " 00:00:00"
    #         if "FEB" in sWord and not sWord.startswith("FEB"):
    #             return sWord[-4:] + "-02-" + sWord[:2] + " 00:00:00"
    #         if "MAR" in sWord and not sWord.startswith("MAR"):
    #             return sWord[-4:] + "-03-" + sWord[:2] + " 00:00:00"
    #         if "APR" in sWord and not sWord.startswith("APR"):
    #             return sWord[-4:] + "-04-" + sWord[:2] + " 00:00:00"
    #         if "MEI" in sWord and not sWord.startswith("MEI"):
    #             return sWord[-4:] + "-05-" + sWord[:2] + " 00:00:00"
    #         if "JUN" in sWord and not sWord.startswith("JUN"):
    #             return sWord[-4:] + "-06-" + sWord[:2] + " 00:00:00"
    #         if "JUL" in sWord and not sWord.startswith("JUL"):
    #             return sWord[-4:] + "-07-" + sWord[:2] + " 00:00:00"
    #         if "AGU" in sWord and not sWord.startswith("AGU"):
    #             return sWord[-4:] + "-08-" + sWord[:2] + " 00:00:00"
    #         if "SEP" in sWord and not sWord.startswith("SEP"):
    #             return sWord[-4:] + "-09-" + sWord[:2] + " 00:00:00"
    #         if "OKT" in sWord and not sWord.startswith("OKT"):
    #             return sWord[-4:] + "-10-" + sWord[:2] + " 00:00:00"
    #         if "NOV" in sWord and not sWord.startswith("NOV"):
    #             return sWord[-4:] + "-11-" + sWord[:2] + " 00:00:00"
    #         if "DES" in sWord and not sWord.startswith("DES"):
    #             return sWord[-4:] + "-12-" + sWord[:2] + " 00:00:00"
    #         if sWord.startswith("APR"):
    #             return sWord[-4:] + "-04-01 00:00:00"
    #         if sWord.startswith("MAR"):
    #             return sWord[-4:] + "-03-01 00:00:00"
    #         else:
    #             return ""
    
    if len(sWord) == 9:
        if "JAN" in sWord and not sWord.startswith("JAN"):
            return sWord[-4:] + "-01-01 00:00:00"
        if "FEB" in sWord and not sWord.startswith("FEB"):
            return sWord[-4:] + "-02-01 00:00:00"
        if "MAR" in sWord and not sWord.startswith("MAR"):
            return sWord[-4:] + "-03-01 00:00:00"
        if "APR" in sWord and not sWord.startswith("APR"):
            return sWord[-4:] + "-04-01 00:00:00"
        if "MEI" in sWord and not sWord.startswith("MEI"):
            return sWord[-4:] + "-05-01 00:00:00"
        if "JUN" in sWord and not sWord.startswith("JUN"):
            return sWord[-4:] + "-06-01 00:00:00"
        if "JUL" in sWord and not sWord.startswith("JUL"):
            return sWord[-4:] + "-07-01 00:00:00"
        if "AGU" in sWord and not sWord.startswith("AGU"):
            return sWord[-4:] + "-08-01 00:00:00"
        if "SEP" in sWord and not sWord.startswith("SEP"):
            return sWord[-4:] + "-09-01 00:00:00"
        if "OKT" in sWord and not sWord.startswith("OKT"):
            return sWord[-4:] + "-10-01 00:00:00"
        if "NOV" in sWord and not sWord.startswith("NOV"):
            return sWord[-4:] + "-11-01 00:00:00"
        if "DES" in sWord and not sWord.startswith("DES"):
            return sWord[-4:] + "-12-01 00:00:00"
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
    
        
    print("--------TextResult---------")
    print(textResult)
    print("---------END----------")
    
    
    print("--------SLINES---------")
    print(sLines)
    print("---------END----------")

    readMethod = ReadMethod.InLine
    for sLine in sLines:
        if "SPBU" in sLine.upper() or "PERTAMINA" in sLine.upper() or "VIVO" in sLine.upper() or "SHELL" in sLine.upper() or "PERTALITE" in sLine.upper() or "SOLAR" in sLine.upper() or "PERTAMAX" in sLine.upper() or "DEXLITE" in sLine.upper() or "SOLAR" in sLine.upper():
            type = "Bensin"
            readMethod = ReadMethod.InLine
            break
        elif "PDAM" in sLine.upper() or "AIR" in sLine.upper():
            type = "PDAM_Postpaid"
            readMethod = ReadMethod.InLine
            break
        # elif "RIWAYAT" in sLine.upper().replace(" ", "") and "TOKEN" in sLine.upper().replace(" ", ""):
        elif "PRABAYAR" in sLine.upper().replace(" ", ""):
            type = "Prepaid"
            readMethod = ReadMethod.Grid
            break
        # elif "ID" in sLine.upper().replace(" ", "") and "PELANGGAN" in sLine.upper().replace(" ", ""):
        elif "PASCABAYAR" in sLine.upper().replace(" ", ""):
            type = "Postpaid"
            readMethod = ReadMethod.Grid
            break
        
    
    # Jika Metode Slines tidak terdeteksi maka akan memakai textResult    
    for tResult in textResult:
        if "SPBU" in sLine.upper() or "PERTAMINA" in sLine.upper() or "VIVO" in sLine.upper() or "SHELL" in sLine.upper() or "PERTALITE" in sLine.upper() or "SOLAR" in sLine.upper() or "PERTAMAX" in sLine.upper() or "DEXLITE" in sLine.upper() or "SOLAR" in sLine.upper():
            type = "Bensin"
            readMethod = ReadMethod.InLine
            break
        elif "PDAM" in tResult.upper() or "AIR" in tResult.upper():
            type = "PDAM_Postpaid"
            readMethod = ReadMethod.InLine
            break
        # elif "RIWAYAT" in tResult.upper().replace(" ", "") and "TOKEN" in tResult.upper().replace(" ", ""):
        elif "PRABAYAR" in tResult.upper().replace(" ", ""):
            type = "Prepaid"
            readMethod = ReadMethod.Grid
            break
        # elif "ID" in tResult.upper().replace(" ", "") and "PELANGGAN" in tResult.upper().replace(" ", ""):
        elif "PASCABAYAR" in tResult.upper().replace(" ", ""):
            type = "Postpaid"
            readMethod = ReadMethod.Grid
            break

    sWords = []
    field = ""
    if type == "Bensin": #Using textResult
        for i in range(len(textResult)):
            sLine = textResult[i]
            # sLine = sLine.replace(" ", "")
            if "PRODUK" in sLine.upper() or "JENIS BBM" in sLine.upper() or "NAMA PRODUK" in sLine.upper() or "PRODUCT" in sLine.upper() or "Jenis BEN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    product = get_product_BBM(sLine)
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "PRODUCT" in sLine.upper() or "GRADE" in sLine.upper() or "Jenis BEN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    product = get_product_BBM_V2(sLines[i-0])
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "PRODUCT" in sLine.upper() or "GRADE" in sLine.upper() or "GRADE " in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product != "PERTALITE":
                        product = get_product_BBM_V3(sLines[i-2])
                    else :
                        product = get_product_BBM_V3(sLines[i-0])
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "HARGA/LITER" in sLine.upper() or "PRICE" in sLine.upper() or "UNIT PRICE" in sLine.upper() :
                if readMethod == ReadMethod.InLine:
                    price = get_price(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "price"
            if isVolume(sLine.replace(" ", "")) == True or isVolume(sLine.replace(",", ".")) == True:
                if('HARGA/LITER' not in sLine.upper()):
                    if readMethod == ReadMethod.InLine:
                        if sLine == "Jml Liter" :
                            sLine = sLines[13]
                            quantity = get_quantity(sLine)
                                                    
                        if sLine != "Jml Liter" :
                            quantity = get_quantity(sLine)
                    elif readMethod == ReadMethod.LineBelow:
                        field = "quantity"
                        
            if "RUPIAH" in sLine.upper() or "TOTAL HARGA" in sLine.upper() or "TOTAL" in sLine.upper() or "AMOUNT(RP" in sLine.upper() or "AMOUNT" in sLine.upper(): 
                print("Masuk Total : " + sLine)

                if readMethod == ReadMethod.InLine:
                    total = get_total(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
            if "TANGGAL" in sLine.upper() or "WAKTU" in sLine.upper() or "AKTU" in sLine.upper()  or "SUN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if sLine == "Waktu" or sLine == "Tanggal" or sLine == "Date" or sLine == "Vaktu":
                        print("MASUKK SATU :",sLine,"KO")
                        getTanggal = sLines[2]
                        #for Hp Oppo
                        if "SHIFT" in getTanggal.upper():
                            getTanggal = sLines[4]
                        
                        tanggal = get_tanggal_BBM_V3(getTanggal)
                        # tanggal = get_tanggal_BBM(sLine)
                        len_tanggal = len(tanggal)
                        if len_tanggal == 10:
                            getWaktu = sLines[i+0].split(": ")
                            print("BDUIBIUBDSBD : ", getWaktu)
                            result = getWaktu[0]
                            if(len(getWaktu) == 2) :
                                result = getWaktu[1]
                                
                            result = re.sub(r'[a-zA-Z]', '', result)    
                            tanggal = get_waktu(result, tanggal)
                            # tanggal = get_waktu(result, tanggal)
                        # return tanggal
                        
                    if sLine != "Waktu" and sLine.replace(" ", "") != "Vaktu":
                        print("BUKA VAKTU", sLine)
                        tanggal = get_tanggal_BBM(sLine)
                        len_tanggal = len(tanggal)
                        if len_tanggal == 10:
                            tanggal = get_waktu(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"        
            if "DATE" in sLine.upper(): 
                if readMethod == ReadMethod.InLine:
                    tanggal = get_tanggal_BBM_V2(sLine)
                    len_tanggal = len(tanggal)
                    if len_tanggal == 10:
                        tanggal = get_waktu_V2(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if "SUN" in sLine.upper() or "MON" in sLine.upper() or "TUE" in sLine.upper() or "WED" in sLine.upper() or "THU" in sLine.upper() or "FRI" in sLine.upper() or "SAT" in sLine.upper(): 
                if readMethod == ReadMethod.InLine:
                    tanggal = getTanggalShell(sLine)
                    len_tanggal = len(tanggal)
                    if len_tanggal == 10:
                        tanggal = get_waktu_V2(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            
            if "SENIN" in sLine.upper() or "SELASA" in sLine.upper() or "RABU" in sLine.upper() or "KAMIS" in sLine.upper() or "JUMAT" in sLine.upper() or "SABTU" in sLine.upper() or "MINGGU" in sLine.upper(): 
                print("Get Tanggal 3 : " + sLine)
                
                if readMethod == ReadMethod.InLine:
                    tanggal = getTanggalBBMV3(sLine)
                    print("TANGGAALALLLLLLLLLLLLLLL")
                    print(tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            
            if isTanggal(sLine.upper())== True:
                print("Get Tanggal 4 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    tanggal = GetDate_Nokey(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if isTanggal(sLine.upper()) == True:
                print("Get Tanggal 5 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    tanggal = GetDate_Nokey_V2(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if validate_shell_date(sLine.upper()):
                print("Get Tanggal 6 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    tanggal =  get_waktu(sLines[i+0], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            
            if validate_nokey_v3(sLine.upper()):
                print("Get Tanggal 7 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    # tanggal =  get_waktu(sLines[i+0], tanggal)
                    tanggal = get_waktu(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if "PLAT" in sLine.upper() or "NO. PLAT" in sLine.upper()  or "NO PLAT" in sLine.upper() or "VEHICLE NO" in sLine.upper() or "NO. KEND." in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    name = get_namePlat(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "name"
                    
    elif type == "PDAM_Postpaid": #Using textResult
        for i in range(len(textResult)):
            sLine = textResult[i]
            # sLine = sLine.replace(" ", "")
            if "NAMA INSTANSI" in sLine.upper() or "NAMA PDAM" in sLine.upper() or "PDAM" in sLine.upper() or "PRODUK" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    product = get_name_pdam(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "NAMA" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product == "":
                        # product = get_custname(sLine)
                        custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "custname"
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
            if "TAGIHAN AKHIR" in sLine.upper() or "TOTAL BAYAR" in sLine.upper() or "TOTAL TAGIHAN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    total = get_price(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
            if "TAGIHAN AKHIR" in sLine.upper() or "TOTAL BAYAR" in sLine.upper() or "TOTAL TAGIHAN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    total = get_total(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
                    
            if isTanggal(sLine.upper())== True:
                if readMethod == ReadMethod.InLine:
                    tanggal = GetDate_Nokey(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if "NO PEL/SAMB" in sLine.upper() or "No. Pelanggan" in sLine.upper() or "NO PELANGGAN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    name = get_noPelanggan(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "name"
        
        # for i in range(len(sLines)):
        #     sLine = sLines[i]

        #     if readMethod == ReadMethod.LineBelow and field:
        #         if field == "name":
        #             # name = get_noPelanggan(sLine)
        #             custname = get_custname(sLines[i-2], textResult)
        #         elif field == "price":
        #             price = get_name_pdam(sLine, False)
        #         elif field == "quantity":
        #             quantity = get_quantity(sLine)
        #         elif field == "total":
        #             total = get_total(sLine)
        #         elif field == "tanggal":
        #             tanggal = get_tanggal(sLine)

        #         field = ""
        #         continue

        #     if readMethod == ReadMethod.Grid:
        #         line = lines[i]
        #         line["words"].sort(key=lambda word: word["minX"])
        #         sWord = ""
        #         lastMaxX = 0
        #         lastMinX = 0
        #         for word in line["words"]:
        #             if lastMaxX == 0:
        #                 lastMaxX = word["maxX"]
        #                 lastMinX = word["minX"]
        #                 for symbol in word["symbols"]:
        #                     sWord = sWord + symbol.text
        #             elif lastMaxX + ((lastMaxX - lastMinX) / len(sWord) if len(sWord) > 0 else 0) < word["minX"]:
        #                 sWords.append(sWord)
        #                 sWord = ""
        #                 for symbol in word["symbols"]:
        #                     sWord = sWord + symbol.text
        #                 lastMaxX = word["maxX"]
        #                 lastMinX = word["minX"]
        #             else:
        #                 for symbol in word["symbols"]:
        #                     sWord = sWord + symbol.text
        #                 lastMaxX = word["maxX"]
        #         if sWord:
        #             sWords.append(sWord)
    
    elif type == "Prepaid" or type == "Postpaid":              
        for i in range(len(sLines)):
            sLine = sLines[i]

            if readMethod == ReadMethod.LineBelow and field:
                if field == "name":
                    name = get_name(sLine)
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
            if sWord.count('-') == 2 and not re.match("[a-zA-Z:]", sWord):
                name = sWord
                for i in range(len(sLines)):
                    if(sLines[i-1].find('RW.')!= -1 or sLines[i-1].find('RT.')!= -1 or sLines[i-1].find('No.')!= -1):
                        if name in sLines[i]:
                            custname = get_custname(sLines[i-2],textResult)
                        if name in sLines[i]:
                            custaddress = get_address(sLines[i-1],textResult)
                    else:
                        isFind = False
                        indexFind = -1
                        for indexResult in range(len(textResult)):
                            if(textResult[indexResult].find('RW.')!= -1 or textResult[indexResult].find('No.')!= -1 or textResult[indexResult].find('RT.')!= -1 or textResult[indexResult].find('JL')!= -1 or textResult[indexResult].find('JL.')!= -1):
                                isFind = True
                                indexFind = indexResult
                        if(isFind):
                            custaddress = textResult[indexFind]
                            custname = textResult[indexFind - 1]
                        else:
                            if name in sLines[i]:
                                print(get_word_array(lines[i-2]))
                                print("get array customer name")
                                #existing oleh Maul 06/06/23
                                # custname = get_custname(sLines[i-1],textResult)
                                                            
                                #new
                                if isFind  == True :
                                    custname = get_custname(sLines[i-1],textResult)
                                else:
                                    custname = textResult[2]
                                # custname = textResult[2]
                                
                            if name in sLines[i]:
                                print(get_word_array(lines[i]))
                                print("get array customer address")
                                custaddress = get_address(sLines[i-1],textResult)
                                
                                #existing oleh Maul 06/06/23
                                # custaddress = get_address(sLines[i-1],textResult)

                                #new
                                if isFind  == True :
                                    custaddress = get_address(sLines[i-2],textResult)
                                else:
                                    custaddress = textResult[3].replace("*", "")

            elif "PRABAYAR" in sWord.upper() or "PASCABAYAR" in sWord.upper():
                # tempProduct = sWord.upper().replace("PRABAYAR", "").replace("PASCABAYAR", "").replace("/", "").replace(" ", "")
                # product = ""
                # digitCounter = 0
                # for i in range(len(tempProduct)):
                #     if tempProduct[i].isdigit():
                #         digitCounter = digitCounter + 1
                #         if digitCounter > 1:
                #             product = product + "/" + tempProduct[i:]
                #             break
                #         else:
                #             product = product + tempProduct[i]
                #     else:
                #         product = product + tempProduct[i]

                product = "Electricity"

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
                    print("sWord Tanggal: " + sWord)
                    sTanggal = GetDate(sWord)
                    
                if sTanggal and sTotal and sQuantity:
                    listTransaction.append(ResultData(sTanggal, sTotal, sQuantity))
                    sTanggal = ""
                    sTotal = ""
                    sQuantity = ""
            elif type == "Postpaid":
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
            if "PRODUK" in sLine.upper() or "JENIS BBM" in sLine.upper() or "NAMA PRODUK" in sLine.upper() or "GRADE" in sLine.upper() or "PRODUCT" in sLine.upper() or "JENISBEN" in sLine.upper() or "RODUK" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product == "":
                        product = get_product_BBM(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "PRODUCT" in sLine.upper() or "GRADE" in sLine.upper() or "JENIS BBM" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product == "":
                        product = get_product_BBM_V2(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "PRODUCT" in sLine.upper() or "GRADE" in sLine.upper() or "GRADE " in sLine.upper() or "JENISBBM" in sLine.upper() or "JENIS BBM" in sLine.upper() :
                if readMethod == ReadMethod.InLine:
                    if product != "PERTALITE":
                        product = get_product_BBM_V3(sLine).replace("JenisBBM:SOLAR", "SOLAR")
                        # product = get_product_BBM_V3(sLine)
                    else :
                        product = get_product_BBM_V3(sLines[i-0])
                    # custname = get_custname(sLines[i-2], textResult)
            if "HARGA/LITER" in sLine.upper() or "UNIT PRICE" in sLine.upper() or "PRICE" in sLine.upper():
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
            if("VOLUME" in sLine.upper()):
                if readMethod == ReadMethod.InLine:
                    if quantity == "":
                        quantity = get_quantity(sLines[i+5])
                elif readMethod == ReadMethod.LineBelow:
                    field = "quantity"
                    
            if "RUPIAH" in sLine.upper() or "TOTAL HARGA" in sLine.upper() or "TOTAL" in sLine.upper() or "AMOUNT(RP" in sLine.upper() or "AMOUNT" in sLine.upper(): 
                if readMethod == ReadMethod.InLine:
                    if total == "":
                        total = get_total(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
                    
            # if "RUPIAH" in sLine.upper() or "TOTAL HARGA" in sLine.upper() or "TOTAL" in sLine.upper() or "AMOUNT" in sLine.upper():
            #     if readMethod == ReadMethod.InLine:
            #         total = get_total(sLine)
            #         print("total from Slinis 2 : ")
            #         print(total)
            #     elif readMethod == ReadMethod.LineBelow:
            #         field = "total"
            # if "AMOUNT" in sLine.upper(): 
            #     if readMethod == ReadMethod.InLine:
            #         if total == "":
            #             total = get_total(sLines[i+4])
            #     elif readMethod == ReadMethod.LineBelow:
            #         field = "total"
            if validate_datetime(sLine.upper()):
                print("Get Tanggal from Sline : " + sLine)
                if readMethod == ReadMethod.InLine:
                    # tanggal =  get_waktu(sLines[i+0], tanggal)
                   len_tanggal = len(tanggal)
                   if len_tanggal == 10:
                        tanggal = get_waktuV2(sLine, tanggal)
                    # tanggal = get_waktu(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if "TANGGAL" in sLine.upper() or "WAKTU" in sLine.upper() or "AKTU" in sLine.upper() or "DATE" in sLine.upper() or "VAKTU" in sLine.upper(): 
                print("Get Tanggal from Sline 2 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    if "VAKTU" in sLine.upper():
                            print("Masuk Vaktu")
                            print(sLine)
                            getTanggal = sLines[2]
                            tanggal = get_tanggal_BBM_V3(getTanggal.replace("-","/").replace(" fi", ""))
                            # tanggal = get_tanggal_BBM(sLine)
                            len_tanggal = len(tanggal)
                            
                    if tanggal == "":
                        print("BUKAAA DUA:")
                        tanggal = get_tanggal_BBM(sLine).replace(" fi", "")
                        len_tanggal = len(tanggal)
                        if len_tanggal == 10:
                            tanggal = get_waktu(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if "VAKTU" in sLine.upper(): 
                print("Get Tanggal from Sline VAKTU : " + sLine)
                if readMethod == ReadMethod.InLine:
                    if "VAKTU" in sLine.upper():
                            print("Masuk Vaktu")
                            print(sLine)
                            getTanggal = sLines[2]
                            tanggal = get_tanggal_BBM_V3(getTanggal.replace("-","/").replace(" fi", ""))
                            # tanggal = get_tanggal_BBM(sLine)
                            len_tanggal = len(tanggal)
                            if len_tanggal == 10:
                                getWaktu = sLines[i+0].split(": ")
                                result = getWaktu[1]
                                tanggal = get_waktu(result.replace(" fi", ""), tanggal)
                            
                    if tanggal == "":
                        tanggal = get_tanggal_BBM_V3(getTanggal.replace("-","/").replace(" fi", ""))
                        # tanggal = get_tanggal_BBM(sLine)
                        len_tanggal = len(tanggal)
                        if len_tanggal == 10:
                            tanggal = get_waktu(sLines[i+1], tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
                    
            if isTanggal(sLine.upper()) == True:
                print("Get Tanggal from Sline 3 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    if tanggal == "":
                        tanggal = GetDate_Nokey(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if "PLAT" in sLine.upper() or "NO. PLAT" in sLine.upper() or "NO PLAT" in sLine.upper() or "VEHICLE NO" in sLine.upper() or "NO. KEND." in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if name == "":
                        name = get_namePlat(sLine)
                        # print("plat",sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "name"
                    
    # add
    
    if type == "PDAM_Postpaid": #Using sLines
        for i in range(len(sLines)):
            sLine = sLines[i]
            # sLine = sLine.replace(" ", "")
            if "NAMA INSTANSI" in sLine.upper() or "NAMA PDAM" in sLine.upper() or "NAMA" in sLine.upper() or "PDAM" in sLine.upper() or "PRODUK" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product == "":
                        product = get_name_pdam(sLine)
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "product"
            if "NAMA" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if product == "":
                        product = get_custname(sLine)
                    # custname = get_custname(sLines[i-2], textResult)
                elif readMethod == ReadMethod.LineBelow:
                    field = "custname"
            if "TAGIHAN" in sLine.upper() or "TOTAL" in sLine.upper() or "TAGIHAN AIR" in sLine.upper() or "TOTAL TAGIHAN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if price == "":
                        price = get_price(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "price"
            if isVolume(sLine.replace(" ", "")) == True or "JUMLAH PAKAI" in sLine.upper() or "PEMAKAIAN" in sLine.upper() :
                if('HARGA/LITER' not in sLine.upper()):
                    if readMethod == ReadMethod.InLine:
                        if quantity == "":
                            quantity = get_quantity(sLine)
                    elif readMethod == ReadMethod.LineBelow:
                        field = "quantity"
            if "TAGIHAN" in sLine.upper() or "TOTAL" in sLine.upper() or "TAGIHAN AIR" in sLine.upper() or "TOTAL TAGIHAN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if total == "":
                        total = get_total(sLine)
                elif readMethod == ReadMethod.LineBelow:
                    field = "total"
            # if "TANGGAL" in sLine.upper() or "WAKTU" in sLine.upper() or "AKTU" in sLine.upper():
            #     if readMethod == ReadMethod.InLine:
            #         if tanggal == "":
            #             tanggal = get_tanggal_BBM(sLine)
            #             len_tanggal = len(tanggal)
            #             if len_tanggal == 10:
            #                 tanggal = get_waktu(sLines[i+1], tanggal)
            #     elif readMethod == ReadMethod.LineBelow:
            #         field = "tanggal"
            if isTanggal(sLine.upper())== True:
                print("Masuk 5 : " + sLine)
                if readMethod == ReadMethod.InLine:
                    if tanggal == "":
                        tanggal = GetDate_Nokey(sLine, tanggal)
                elif readMethod == ReadMethod.LineBelow:
                    field = "tanggal"
            if "NO PEL/SAMB" in sLine.upper() or "NO. PELANGGAN" in sLine.upper() or "NO PELANGGAN" in sLine.upper():
                if readMethod == ReadMethod.InLine:
                    if name == "":
                        name = get_noPelanggan(sLine)
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

def get_orientation(response):
    '''
    get orientation

    response: VisionAI response

    returns:
        orientation angle
    '''

    MIN_WORD_LENGTH_FOR_ROTATION_INFERENCE = 4

    orientations = []

    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            for paragraph in block.paragraphs:
                for word in paragraph.words:
                    if len(word.symbols) < MIN_WORD_LENGTH_FOR_ROTATION_INFERENCE:
                        continue
                    first_char = word.symbols[0]
                    last_char = word.symbols[-1]
                    first_char_center = (np.mean([v.x for v in first_char.bounding_box.vertices]), np.mean(
                        [v.y for v in first_char.bounding_box.vertices]))
                    last_char_center = (np.mean([v.x for v in last_char.bounding_box.vertices]), np.mean(
                        [v.y for v in last_char.bounding_box.vertices]))

                    # upright or upside down
                    top_right = last_char.bounding_box.vertices[1]
                    bottom_right = last_char.bounding_box.vertices[2]
                    if np.abs(first_char_center[1] - last_char_center[1]) < np.abs(top_right.y - bottom_right.y):
                        if first_char_center[0] <= last_char_center[0]:  # upright
                            orientations.append(0)
                            # print(0)
                        else:  # updside down
                            orientations.append(180)
                            # print(180)
                    else:  # sideways
                        if first_char_center[1] <= last_char_center[1]:
                            orientations.append(90)
                            # print(90)
                        else:
                            orientations.append(270)
                            # print(270)
    return orientations

def img_to_bytes(img):
    '''
    convert PIL image variable to bytes

    img: PIL Image

    returns:
        image bytes
    '''

    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    img_byte_arr = img_byte_arr.getvalue()
    return img_byte_arr

class VisionAll(Resource):
    def __init__(self):
        self.parser = reqparse.RequestParser()

    def get(self):
        msg = "VisionAPI " + APPVersion
        return msg, 200
    
    def post(self):
        self.parser.add_argument('image', type=werkzeug.datastructures.FileStorage, location='files')
        
        args = self.parser.parse_args()
        
        image = args["image"]
        img = image
        # img = Image.open(io.BytesIO(image))
        client = vision.ImageAnnotatorClient()
        response = client.text_detection(image=image)
        
        image_file = Image.open(img)

        # correcting orientation
        orientations = get_orientation(response)
        orientation = np.median(orientations)

        if orientation == 90:
            image = image_file.rotate(90, expand=True) 
            image_bytes = img_to_bytes(image) 
            image_vision = vision.Image(content=image_bytes)

            response = client.text_detection(image=image_vision)
        elif orientation == 180:
            image = image_file.rotate(180, expand=True)
            image_bytes = img_to_bytes(image) 
            image_vision = vision.Image(content=image_bytes)

            response = client.text_detection(image=image_vision)
        elif orientation == 270:
            image = image_file.rotate(270, expand=True)
            image_bytes = img_to_bytes(image) 
            image_vision = vision.Image(content=image_bytes)

            response = client.text_detection(image=image_vision)

        # if not os.path.isdir("Image"):
        #     os.mkdir("Image")
            
        # image.save('Image' + '/' + img.filename)
        image_file.close()

        document = response.full_text_annotation

        result = extract_text(document)

        return result.to_json(), 200
