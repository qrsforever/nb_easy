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


def nbeasy_imread(imgin, color='rgb', size=None):
    is_bytes = isinstance(imgin, bytes)
    if is_bytes or imgin.startswith('http'):
        if not is_bytes:
            response = requests.get(imgin)
            if response:
                imgin = response.content
            else:
                raise
        img = cv2.imdecode(np.frombuffer(imgin, dtype=np.uint8), cv2.IMREAD_COLOR)
        if color != 'rgb':
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        elif color == 'gray':
            img = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    else:
        img = cv2.imread(imgin)
        if color == 'rgb':
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        elif color == 'gray':
            img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if size:
        if isinstance(size, int):
            size = (size, size)
        img = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
    return img


def nbeasy_imshow(image, title=None, color='rgb', figsize=(6, 3), canvas=False):
    import IPython
    plt.close('all')
    if figsize == 'auto':
        ih, iw = image.shape[:2]
        fw, fh = int(1.5 * iw / 80) + 1, int(1.5 * ih / 80) + 1
        if fw > 32:
            fh = int(32 * (fh / fw))
            fw = 32
        figsize = (fw, fh)
    if canvas:
        IPython.get_ipython().enable_matplotlib(gui='widget');
        fig = plt.figure(figsize=figsize)
        fig.canvas.toolbar_position = 'left'
        fig.canvas.toolbar_visible = True
        fig.canvas.header_visible = False
        fig.canvas.footer_visible = True
    else:
        IPython.get_ipython().enable_matplotlib(gui='inline')
        fig = plt.figure(figsize=figsize)
    plt.axis('off')
    if title is not None:
        plt.title(title)
    if color == 'gray' or len(image.shape) == 2:
        plt.imshow(image, cmap='gray');
    else:
        if color == 'bgr':
           image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        plt.imshow(image);


def nbeasy_imgrid(images, nrow=None, padding=4, pad_value=127, labels=None,
                     font_scale=1.0, font_thickness=1, text_color=(255,), text_color_bg=None):
    count = len(images)
    if isinstance(images, dict):
        labels = [lab for lab in images.keys()]
        images = [img for img in images.values()]

    if not isinstance(images, (list, tuple, np.ndarray)) or count == 0 or not isinstance(images[0], np.ndarray):
        return
    if nrow is None or nrow > count:
        nrow = count

    max_h, max_w = np.asarray([img.shape[:2] for img in images]).max(axis=0)
    if labels is not None:
        text_org = int(0.1 * max_w), int(0.9 * max_h)
        shape_length = 3
    else:
        shape_length = np.asarray([len(img.shape) for img in images]).max()
    lack = count % nrow
    rows = np.intp(np.ceil(count / nrow))
    hpad_size = [max_h, padding]
    if rows > 1:
        vpad_size = [padding, nrow * max_w + (nrow - 1) * padding]
        if lack > 0:
            lack_size = [max_h, max_w]
    if shape_length == 3:
        hpad_size.append(3)
        if rows > 1:
            vpad_size.append(3)
            if lack > 0:
                lack_size.append(3)
    hpadding = pad_value * np.ones(hpad_size, dtype=np.uint8)
    if rows > 1:
        vpadding = pad_value * np.ones(vpad_size, dtype=np.uint8)
        if lack > 0:
            lack_image = pad_value * np.ones(lack_size, dtype=np.uint8)
            images.extend([lack_image] * lack)
            if labels is not None:
                labels.extend([''] * lack)
    vlist = []
    for i in range(rows):
        hlist = []
        for j in range(nrow):
            if j != 0:
                hlist.append(hpadding)
            timg = images[i * nrow + j].copy()
            th, tw = timg.shape[:2]
            if th != max_h or tw != max_w:
                timg = cv2.resize(timg, (max_w, max_h))
            if len(timg.shape) != shape_length:
                timg = cv2.cvtColor(timg, cv2.COLOR_GRAY2BGR)
            if labels is not None:
                text = str(labels[i * nrow + j])
                if len(text) > 0:
                    if text_color_bg is not None:
                        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, font_thickness)
                        pos1 = text_org[0] - int(font_scale * 5), text_org[1] - th - int(font_scale * 5)
                        pos2 = text_org[0] + int(font_scale * 5) + tw, text_org[1] + int(font_scale * 8)
                        cv2.rectangle(timg, pos1, pos2, text_color_bg, -1)
                    cv2.putText(timg, text, text_org, cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, font_thickness)
            hlist.append(timg)
        if i != 0:
            vlist.append(vpadding)
        vlist.append(np.hstack(hlist))
    if rows > 1:
        return np.vstack(vlist)
    return vlist[0]
