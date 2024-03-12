#!/usr/bin/python3
# -*- coding: utf-8 -*-

# @file easy_show.py
# @brief
# @author QRS
# @blog qrsforever.gitee.io
# @version 1.0
# @date 2022-01-24 14:23

import json, base64, requests # noqa
import numpy as np
import cv2
import matplotlib.pyplot as plt


def nbeasy_show_table(headers, data, width=900):
    from IPython.display import Markdown
    ncols = len(headers)
    width = int(width / ncols)
    lralign = []
    caption = []
    for item in headers:
        astr = ''
        if item[0] == ':':
            astr = ':'
            item = item[1:]
        astr += '---'
        if item[-1] == ':':
            astr += ':'
            item = item[:-1]
        lralign.append(astr)
        caption.append(item)
    captionstr = '|'.join(caption) + chr(10)
    lralignstr = '|'.join(lralign) + chr(10)
    imgholdstr = '|'.join(['<img width=%d/>' % width] * ncols) + chr(10)
    table = captionstr + lralignstr + imgholdstr
    is_dict = isinstance(data[0], dict)
    for row in data:
        if is_dict:
            table += '|'.join([f'{row[c]}' for c in caption]) + chr(10)
        else:
            table += '|'.join([f'{col}' for col in row]) + chr(10)
    return Markdown(table)


def nbeasy_show_imread(path, rgb=True, size=None):
    if path.startswith('http'):
        response = requests.get(path)
        if response:
            imgmat = np.frombuffer(response.content, dtype=np.uint8)
            img = cv2.imdecode(imgmat, cv2.IMREAD_COLOR)
    else:
        img = cv2.imread(path)

    if rgb:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    if size:
        if isinstance(size, int):
            size = (size, size)
        img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
    return img


def nbeasy_show_plot(imgsrc, width=None, height=None):
    from IPython.display import HTML
    if isinstance(imgsrc, np.ndarray):
        img = imgsrc
        if width or height:
            if width and height:
                size = (width, height)
            else:
                rate = img.shape[1] / img.shape[0]
                if width:
                    size = (width, int(width/rate))
                else:
                    size = (int(height*rate), height)
            img = cv2.resize(img, size)
            plt.figure(figsize=(3*int(size[0]/80+1), 3*int(size[1]/80+1)), dpi=80)
        plt.axis('off')
        if len(img.shape) > 2:
            plt.imshow(img)
        else:
            plt.imshow(img, cmap='gray')
        return

    W, H = '', ''
    if width:
        W = 'width=%d' % width
    if height:
        H = 'height=%d' % height
    if imgsrc.startswith('http'):
        data_url = imgsrc
    else:
        if len(imgsrc) > 2048:
            data_url = 'data:image/jpg;base64,' + imgsrc
        else:
            img = open(imgsrc, 'rb').read()
            data_url = 'data:image/jpg;base64,' + base64.b64encode(img).decode()
    return HTML('<center><img %s %s src="%s"/></center>' % (W, H, data_url))


def nbeasy_hstack(imglist, sep=10, color=255):
    imgsep = color * np.ones((imglist[0].shape[0], sep, 3), dtype=np.uint8)
    ilist = [imglist[0]]
    for img in imglist[1:]:
        ilist.append(imgsep)
        ilist.append(img)
    return np.hstack(ilist)


def nbeasy_vstack(imglist, sep=10, color=255):
    imgsep = color * np.ones((sep, imglist[0].shape[1], 3), dtype=np.uint8)
    ilist = [imglist[0]]
    for img in imglist[1:]:
        ilist.append(imgsep)
        ilist.append(img)
    return np.vstack(ilist)
