#!/usr/bin/python3
# -*- coding: utf-8 -*-

# @file easy_widget.py
# @brief
# @author QRS
# @blog blog.erlangai.cn
# @version 1.0
# @date 2019-12-18 19:55:57


from IPython.display import display, clear_output
from traitlets.utils.bunch import Bunch
import traitlets
import base64
import requests
import ipywidgets as widgets
import json
import io
import os
import pprint
import copy
import traceback

from pyhocon import ConfigFactory
from pyhocon import HOCONConverter

widgets.Dropdown.value.tag(sync=True)


try:
    is_install_cv2 = False
    import cv2
    import numpy as np
    import matplotlib.pyplot as plt
    is_install_cv2 = True
except Exception:
    pass


def _request_content(url, default=None):
    if isinstance(url, bytes):
        url = url.decode("utf-8", "ignore")
    url = url.strip()
    if url.startswith('http'):
        response = requests.get(url)
        if response:
            return response.content
    elif os.path.isfile(url):
        with open(url, 'rb') as f:
            return f.read()
    return default


def _schema_tooltips(widget_map):# {{{
    tables = []
    for key, wid in widget_map.items():
        if not hasattr(wid, 'description_tooltip') \
                or wid.description_tooltip is None \
                or wid.disabled:
            continue

        if isinstance(wid, widgets.Text):
            if wid.value.startswith('[') and wid.value.endswith(']'):
                value = json.loads(wid.value)
                if isinstance(value[0], int):
                    tables.append((key, wid.description, '整型数组', wid.value, '[int, int, ...]', wid.description_tooltip))
                elif isinstance(value[0], float):
                    tables.append((key, wid.description, '浮点数组', wid.value, '[float, float, ...]', wid.description_tooltip))
            else:
                tables.append((key, wid.description, '字符串', wid.value, '', wid.description_tooltip))
        elif isinstance(wid, widgets.BoundedIntText):
            tables.append((key,
                           wid.description,
                           '整型',
                           wid.value,
                           f'{"(-inf" if wid.min == -2147483647 else "[%d" % wid.min}, {"+inf)" if wid.max == 2147483647 else "%d]" % wid.max}',
                           wid.description_tooltip))
        elif isinstance(wid, widgets.BoundedFloatText):
            tables.append((key,
                           wid.description,
                           '浮点型',
                           wid.value,
                           f'{"(-inf" if wid.min == -2147483647.0 else "[%f" % wid.min}, {"+inf)" if wid.max == 2147483647.0 else "%f]" % wid.max}',
                           wid.description_tooltip))
        elif isinstance(wid, widgets.Checkbox):
            tables.append((key,
                           wid.description,
                           '布尔型',
                           wid.value,
                           '',
                           wid.description_tooltip))
        elif isinstance(wid, widgets.Dropdown):
            for opt in wid.options:
                if opt[1] == wid.value:
                    value = opt[0]
            tables.append((
                key,
                wid.description,
                '枚举型',
                value,
                f'{[o[0] for o in wid.options]}',
                wid.description_tooltip))
    return tables# }}}


def _widget_add_child(widget, wdgs):# {{{
    if not isinstance(wdgs, list):
        wdgs = [wdgs]
    for child in wdgs:
        widget.children = list(widget.children) + [child]
    return widget# }}}


def observe_widget(method):# {{{
    def _widget(self, *args, **kwargs):
        wdg, cb = method(self, *args, **kwargs)
        if self.border:
            wdg.layout.border = '1px solid yellow'

        def _on_value_change(change, cb):
            wdg = change['owner']
            try:
                if hasattr(wdg, 'id'):
                    if isinstance(change['new'], bytes):
                        self.wid_value_map[wdg.id] = change['new'] if len(change['new']) < 256 else change['new'][:16]
                    else:
                        self.wid_value_map[wdg.id] = change['new']
            except Exception:
                self.logger(traceback.format_exc(limit=6))

            if cb:
                try:
                    cb(change)
                except Exception:
                    self.logger(traceback.format_exc(limit=6))
            self._output(change)
        wdg.observe(lambda change, cb=cb: _on_value_change(change, cb), 'value')
        return wdg.parent_box if hasattr(wdg, 'parent_box') else wdg
    return _widget# }}}


class BytesText(widgets.Text):# {{{
    bvalue = traitlets.CBytes(help="Bytes value").tag(sync=True)# }}}


@widgets.register
class ImageA(widgets.Image):# {{{
    url = traitlets.Unicode(help="image url").tag(sync=True)

    def __init__(self, **kwargs):
        width = kwargs.get('width', -1)
        height = kwargs.get('height', -1)
        format = kwargs.get('format', 'url')
        value = kwargs.pop('value', '')
        if format == 'url':
            value = _request_content(value, b'')
        if value and (width < 0 or height < 0):
            img = cv2.imdecode(np.frombuffer(value, dtype=np.uint8), cv2.IMREAD_COLOR)
            height, width = img.shape[:2]
            kwargs['width'] = width
            kwargs['height'] = height
            kwargs['layout'].width = '%dpx' % width
            kwargs['layout'].height = '%dpx' % height
        self.description = ' '
        super().__init__(**kwargs)

        self.format, self.value = 'png', value

    @traitlets.observe('url')
    def _url_to_byte(self, change):
        self.value = _request_content(change['new'].encode('utf-8'), b'')
# }}}


@widgets.register
class ImageE(widgets.Output, widgets.ValueWidget):# {{{
    value = traitlets.CBytes(help="image bytes value").tag(sync=True)

    def __init__(self, dpi=80, **kwargs):
        width = kwargs.get('width', -1)
        height = kwargs.get('height', -1)
        value = kwargs.pop('value', '')
        format = kwargs.get('format', 'url')
        if format == 'url':
            value = _request_content(value, b'')
        if value and (width < 0 or height < 0):
            img = cv2.imdecode(np.frombuffer(value, dtype=np.uint8), cv2.IMREAD_COLOR)
            height, width = img.shape[:2]
            kwargs['width'] = width
            kwargs['height'] = height
        super().__init__(**kwargs)

        self.format, self.value = 'png', value
        self.fig, self.dpi = None, dpi
        self.width, self.height = width, height
        self.description = ' '
        self.imshow()

    def imshow(self, img=None, width=None, height=None):
        if self.fig:
            plt.close(self.fig)
        if width is None:
            width = self.width
        if height is None:
            height = self.height

        self.clear_output()
        with self:
            update_value = True
            if img is None:
                if isinstance(self.value, bytes):
                    if len(self.value) < 256:
                        self.value = _request_content(self.value, b'')
                    img = cv2.imdecode(np.frombuffer(self.value, dtype=np.uint8), cv2.IMREAD_COLOR)
                    update_value = False
                else:
                    print(f'value error:{self.value}')
                    return
            fig, ax = plt.subplots(
                    constrained_layout=True,
                    figsize=(width / self.dpi, height / self.dpi), dpi=self.dpi)
            fig.canvas.toolbar_visible = True
            fig.canvas.header_visible = False
            fig.canvas.footer_visible = True
            fig.canvas.toolbar_position = 'top'
            ax.axis('off')
            if len(img.shape) == 2:
                ax.imshow(img, cmap='gray', vmin=0, vmax=255)
            else:
                ax.imshow(img)
            plt.show(fig)
            if update_value:
                self.value = io.BytesIO(cv2.imencode('.png', img)[1]).getvalue()
            self.fig = fig# }}}


@widgets.register
class VideoA(widgets.Video):# {{{
    url = traitlets.Unicode(help="video url").tag(sync=True)

    @traitlets.observe('url')
    def _url_to_byte(self, change):
        self.value = change['new'].encode('utf-8')
# }}}


@widgets.register
class VideoE(VideoA):# {{{
    """
    detail see custom.js
    """
    _view_name   = traitlets.Unicode('VideoEView').tag(sync=True) # noqa
    _view_module = traitlets.Unicode('VideoEModel').tag(sync=True)
    _view_module_version = traitlets.Unicode('0.1.1').tag(sync=True)

    imgb4str = traitlets.Unicode(help="Image base64 value").tag(sync=True)
    snapshot = traitlets.CBytes(help="Image bytes value").tag(sync=True)

    @traitlets.observe('imgb4str')
    def _img64_to_bytes(self, change):
        self.snapshot = base64.b64decode(self.imgb4str.split(',')[1])

    @classmethod
    def from_file(cls, filename, **kwargs):
        return super(VideoE, cls).from_file(filename, **kwargs)
# }}}


@widgets.register
class AccordionE(widgets.Accordion, widgets.ValueWidget):# {{{
    @traitlets.observe('selected_index')
    def _index_to_value(self, change):
        self.value = change['new']# }}}


@widgets.register
class TabE(widgets.Tab, widgets.ValueWidget):# {{{
    @traitlets.observe('selected_index')
    def _index_to_value(self, change):
        self.value = change['new']# }}}


class WidgetGenerator():
    def __init__(self, lan='en', debug=False, events={}, border=False):# {{{
        self.page = widgets.Box()
        self.out = widgets.Output(
                layout={
                    'border': '1px solid black',
                    'width': '100%', 'height': 'auto', 'max_height': '200px', 'overflow_y': 'scroll'})
        self.output_type = 'none'
        self.lan = lan
        self.tag = 'tag'
        self.defaultconfg = {}
        self.debug = debug
        self.border = border
        self.events = events
        self.source_on_clicks = {}
        self.dataset_dir = ''
        self.dataset_url = ''
        self.basic_types = [
            'int', 'float', 'bool',
            'string', 'label', 'int-array', 'float-array',
            'string-array', 'string-enum', 'image']

        # margin: top, right, bottom, left
        self.vlo = widgets.Layout(
            width='auto',
            align_items='stretch',
            justify_content='flex-start',
            margin='3px 0px 3px 0px')
        if self.border:
            self.vlo.border = 'solid 2px red'

        self.hlo = widgets.Layout(
            width='100%',
            flex_flow='row wrap',
            align_items='stretch',
            justify_content='flex-start',
            margin='3px 0px 3px 0px')
        if self.border:
            self.hlo.border = 'solid 2px blue'

        self.page_layout = widgets.Layout(
            display='flex',
            width='100%')
        if self.border:
            self.page_layout.border = 'solid 2px black'

        self.tab_layout = widgets.Layout(
            display='flex',
            width='99%')
        if self.border:
            self.tab_layout.border = 'solid 2px yellow'

        self.accordion_layout = widgets.Layout(
            display='flex',
            width='99%')
        if self.border:
            self.accordion_layout.border = 'solid 2px green'

        self.nav_layout = widgets.Layout(
            display='flex',
            width='99%',
            margin='3px 0px 3px 0px',
            border='1px solid black')

        self.btn_layout = widgets.Layout(margin='3px 0px 3px 0px')

        self.label_layout = widgets.Layout(
            width="60px",
            justify_content="center")# }}}

    def init_page(self):# {{{
        self.wid_widget_map = {}
        self.wid_value_map = {}# }}}

    def get_widget_byid(self, wid):# {{{
        if wid in self.wid_widget_map:
            return self.wid_widget_map[wid]
        return None# }}}

    def get_widget_defaultconf(self, rmlist=[]):# {{{
        conf = self.defaultconfg.copy()
        if len(rmlist) > 0:
            for wid in rmlist:
                conf.pop(wid, None)
        return conf# }}}

    def set_widget_values(self, jconf):# {{{
        update_items = {}
        for wid, val in jconf.items():
            wdg = self.get_widget_byid(wid)
            if wdg:
                if isinstance(wdg, (widgets.Video, widgets.Image, widgets.Audio)):
                    value = val.encode()
                else:
                    if isinstance(val, (list, tuple)):
                        value = json.dumps(val)
                    else:
                        value = val
                if wdg.value != value:
                    wdg.value = value
                    update_items[wid] = wdg.value
        return update_items# }}}

    def get_all_kv(self, remove_underline=True):# {{{
        kv_map = {}

        def _get_kv(widget):
            if hasattr(widget, 'node_type') and widget.node_type == 'multiselect':
                if hasattr(widget, 'id') and hasattr(widget, 'multi_options'):
                    if widget.id[0] == '_' and widget.id[1] == '_':
                        return
                    if remove_underline and widget.id[0] == '_':
                        return
                    kv_map[widget.id] = widget.get_value()
                return

            if isinstance(widget, widgets.Box):
                if hasattr(widget, 'node_type') and widget.node_type == 'navigation':
                    for child in widget.boxes:
                        _get_kv(child)
                else:
                    for child in widget.children:
                        _get_kv(child)
            else:
                if hasattr(widget, 'id') and hasattr(widget, 'value'):
                    if widget.id[0] == '_' and widget.id[1] == '_':
                        return
                    if remove_underline and widget.id[0] == '_':
                        return

                    value = widget.value
                    if isinstance(value, bytes):
                        value = value.decode("utf-8", "ignore")
                        if len(value) > 512:
                            return
                    if hasattr(widget, 'switch_value'):
                        kv_map[widget.id] = widget.switch_value(value)
                    else:
                        kv_map[widget.id] = value

        _get_kv(self.page)
        return kv_map# }}}

    def get_all_json(self, kvs=None):# {{{
        if not kvs:
            kvs = self.get_all_kv()
        kvs = json.loads(json.dumps(kvs))
        config = ConfigFactory.from_dict(kvs)
        config = HOCONConverter.convert(config, 'json')
        try:
            return json.loads(config)
        except Exception:
            return f'error: {config}'# }}}

    def logger(self, msg, clear=0):# {{{
        with self.out:
            if self.output_type == 'logger':
                if clear:
                    clear_output()
                print(msg)# }}}

    def _output(self, body, clear=1):# {{{
        if self.output_type not in (
                'observe', 'kv', 'kvs', 'json', 'jsons'):
            return
        with self.out:
            if clear:
                clear_output()
            if self.output_type == 'observe':
                if isinstance(body, Bunch):
                    pprint.pprint(body)
                elif isinstance(body, dict):
                    if 'new' in body and isinstance(body['new'], bytes):
                        body['new'] = body['new'] if len(body['new']) < 256 else body['new'][:16]
                    if 'old' in body and isinstance(body['old'], bytes):
                        body['old'] = body['old'] if len(body['old']) < 256 else body['old'][:16]
                    print(json.dumps(body, indent=4, ensure_ascii=False))
                else:
                    print(body)
            elif self.output_type == 'kv':
                pprint.pprint(self.wid_value_map)
            elif self.output_type == 'json':
                config = ConfigFactory.from_dict(self.wid_value_map)
                print(HOCONConverter.convert(config, 'json'))
            elif self.output_type == 'kvs':
                pprint.pprint(self.get_all_kv(False))
            elif self.output_type == 'jsons':
                pprint.pprint(self.get_all_json())# }}}

    @observe_widget
    def Debug(self, description, options, index=0):# {{{
        label = widgets.Label(value=description, layout=self.label_layout)
        wdg = widgets.ToggleButtons(
            options=options,
            index=index,
            # description=description,
            disabled=False,
            button_style='warning')
        wdg.parent_box = widgets.HBox(children=(label, wdg))

        def _value_change(change):
            self.output_type = change['new']
            with self.out:
                clear_output()

        self.output_type = options[index][1]
        return wdg, _value_change# }}}

    def _wid_map(self, wid, widget):# {{{
        if wid:
            widget.id = wid
            widget.context = self
            self.wid_widget_map[wid] = widget# }}}

    def _rm_sub_wid(self, widget):# {{{
        if isinstance(widget, widgets.Box):
            for child in widget.children:
                self._rm_sub_wid(child)
        else:
            if hasattr(widget, 'id'):
                if widget.id in self.wid_value_map.keys():
                    del self.wid_value_map[widget.id]
                if widget.id in self.wid_widget_map.keys():
                    del self.wid_widget_map[widget.id]
# }}}

    @observe_widget
    def Bool(self, wid, *args, **kwargs):# {{{
        wdg = widgets.Checkbox(description_allow_html=True, *args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change# }}}

    @observe_widget
    def Int(self, wid, slider, range, *args, **kwargs):# {{{
        if range:
            wdg = widgets.IntRangeSlider(*args, **kwargs)
        else:
            if slider:
                wdg = widgets.IntSlider(*args, **kwargs)
            else:
                wdg = widgets.BoundedIntText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change# }}}

    @observe_widget
    def Float(self, wid, slider, range, *args, **kwargs):# {{{
        if range:
            wdg = widgets.IntRangeSlider(*args, **kwargs)
        else:
            if slider:
                wdg = widgets.FloatSlider(*args, **kwargs)
            else:
                wdg = widgets.BoundedIntText(*args, **kwargs)
        wdg = widgets.BoundedFloatText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change# }}}

    @observe_widget
    def String(self, wid, *args, **kwargs):# {{{
        wdg = widgets.Text(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change# }}}

    @observe_widget
    def Label(self, wid, *args, **kwargs):# {{{
        wdg = widgets.Label(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change# }}}

    @observe_widget
    def Bytes(self, wid, *args, **kwargs):# {{{
        wdg = BytesText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            change['owner'].bvalue = change['new'].encode('utf-8')

        if 'value' in kwargs:
            wdg.bvalue = kwargs['value'].encode('utf-8')
        return wdg, _value_change# }}}

    @observe_widget
    def Text(self, wid, *args, **kwargs):# {{{
        wdg = widgets.Textarea(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change# }}}

    @observe_widget
    def Array(self, wid, *args, **kwargs):# {{{
        wdg = widgets.Text(*args, **kwargs)
        self._wid_map(wid, wdg)
        wdg.switch_value = lambda val: json.loads(val if (val and val[0] == '[') else '[' + val + ']')

        def _value_change(change):
            wdg = change['owner']
            val = change['new'].strip()
            self.wid_value_map[wdg.id] = wdg.switch_value(val)
        return wdg, _value_change# }}}

    @observe_widget
    def StringEnum(self, wid, *args, **kwargs):# {{{
        wdg = widgets.Dropdown(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change# }}}

    @observe_widget
    def SimpleMultiSelect(self, wid, *args, **kwargs):# {{{
        wdg = widgets.SelectMultiple(*args, **kwargs)
        wdg.switch_value = lambda val: list(val)
        self._wid_map(wid, wdg)

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            self.wid_value_map[wdg.id] = wdg.switch_value(val)
        return wdg, _value_change# }}}

    @observe_widget
    def BoolTrigger(self, wid, triggers, *args, **kwargs):# {{{
        wdg = widgets.Checkbox(*args, **kwargs)
        self._wid_map(wid, wdg)
        parent_box = widgets.VBox(layout=self.vlo)
        parent_box.layout.margin = '3px 0px 6px 0px'
        wdg.parent_box = parent_box
        wdg.triggers = triggers

        def _update_layout(wdg, val, old):
            if old is not None:
                self._rm_sub_wid(wdg.parent_box.children[1])
            trigger_box = widgets.VBox(layout=self.vlo)
            if val:
                self._parse_config(trigger_box, wdg.triggers['true'])
            else:
                self._parse_config(trigger_box, wdg.triggers['false'])
            wdg.parent_box.children = [wdg, trigger_box]

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            old = change['old']
            _update_layout(wdg, val, old)
        _update_layout(wdg, wdg.value, None)
        return wdg, _value_change# }}}

    @observe_widget
    def StringEnumTrigger(self, wid, triggers, *args, **kwargs):# {{{
        wdg = widgets.Dropdown(*args, **kwargs)
        self._wid_map(wid, wdg)
        parent_box = widgets.VBox(layout=self.vlo)
        wdg.parent_box = parent_box
        wdg.triggers = triggers

        def _update_layout(wdg, val, old):
            if old is not None:
                self._rm_sub_wid(wdg.parent_box.children[1])
            trigger_box = widgets.VBox(layout=self.vlo)
            self._parse_config(trigger_box, wdg.triggers[val])
            wdg.parent_box.children = [wdg, trigger_box]

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            old = change['old']
            _update_layout(wdg, val, old)
        _update_layout(wdg, wdg.value, None)
        return wdg, _value_change# }}}

    @observe_widget
    def Image(self, wid, ext, *args, **kwargs):# {{{
        if ext:
            wdg = ImageE(*args, **kwargs)
        else:
            wdg = ImageA(*args, **kwargs)

        wdg.image_data = None
        self._wid_map(wid, wdg)

        def _value_change(change):
            wdg = change['owner']
            new = change['new']
            if len(new) == 0:
                self.logger('Image change value length is 0')
                return
            # think of event links
            if len(new) < 256:
                wdg.value = _request_content(new, b'')

            if isinstance(wdg, ImageE):
                wdg.imshow()
            wdg.image_data = cv2.imdecode(np.frombuffer(wdg.value, dtype=np.uint8), cv2.IMREAD_UNCHANGED)

        return wdg, _value_change# }}}

    def Canvas(self, wid, *args, **kwargs):# {{{
        from ipycanvas import Canvas
        wdg = Canvas(*args, **kwargs, sync_image_data=True)
        wdg.layout.border = '1px solid black'
        self._wid_map(wid, wdg)
        return wdg# }}}

    @observe_widget
    def Video(self, wid, ext, *args, **kwargs):# {{{
        if ext:
            wdg = VideoE(loop=False, autoplay=False, *args, **kwargs)
        else:
            wdg = VideoA(loop=False, autoplay=False, *args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change# }}}

    def _parse_config(self, widget, config):
        __id_ = config.get('_id_', '')
        _name = config.get('name', None)
        _type = config.get('type', None)
        _objs = config.get('objs', None) or []

        if isinstance(_name, str):
            _name = {'en': _name, 'cn': _name}

        description = ' '
        if _name and len(_name[self.lan].strip()) > 0:
            description = _name[self.lan]

        tlo = widgets.Layout()# {{{
        # flex = config.get('flex', '0 1 auto')
        width = config.get('width', None)
        height = config.get('height', None)
        if width:
            if isinstance(width, int):
                tlo.width = '%dpx' % width
            else:
                tlo.width = width
        if height:
            if isinstance(height, int):
                tlo.height = '%dpx' % height
            else:
                tlo.height = height# }}}

        tstyle = {}# {{{
        description_width = config.get('description_width', 130)
        if isinstance(description_width, str):
            tstyle['description_width'] = description_width  # 45% or 'initial'
        else:
            tstyle['description_width'] = '%dpx' % description_width# }}}

        args = {}# {{{
        readonly = config.get('readonly', False)
        default = config.get('default', None)
        if readonly:
            args['disabled'] = True
        if _type in [
                'bool', 'int', 'float', 'string', 'label', 'bytes', 'text', 'string-enum',
                'bool-trigger', 'string-enum-trigger', 'radiobuttons']:
            if default:
                args['value'] = default
        elif _type in ['multiselect_simple', 'multiselect']:
            if default:
                args['index'] = [default] if isinstance(default, int) else default
        tips = config.get('tips', None)
        if tips:
            args['description_tooltip'] = tips# }}}

        if _type in ['int', 'float', 'progressbar']:# {{{
            min = config.get('min', None)
            max = config.get('max', None)
            if min is not None:
                args['min'] = min
            else:
                args['min'] = -2147483647
            if max is not None:
                args['max'] = max
            else:
                args['max'] = 2147483647
            if min and max:
                args['step'] = config.get('step', (max - min) * 0.01) # }}}
        elif _type in ['image', 'audio', 'video', 'canvas']:# {{{
            if width:
                args['width'] = width
            if height:
                args['height'] = height
            format = config.get('format', 'url')
            args['format'] = format
            if format == 'url' and default:
                args['value'] = default.encode('utf-8')# }}}
            else:
                args['value'] = default
        elif _type in ['H', 'V']:# {{{
            # align_content 设置同一列子元素在Y轴的对齐方式
            # justify_content 设置同一行子元素在X轴的对齐方式
            # align_items 设置同一行子元素在Y轴的对齐方式
            # flex-start flex-end center space-between space-around space-evenly stretch inherit initial unset
            tlo.align_items = config.get('align_items', 'stretch')
            tlo.justify_content = config.get('justify_content', 'flex-start')
            tlo.align_content = config.get('align_content', 'flex-start')
            tlo.margin = config.get('margin', '3px 0px 3px 0px')
            if not width:
                tlo.width = '100%'
            if self.border:
                tlo.border = '1px solid cyan'# }}}

        if _type == 'page':# {{{
            wdg = widgets.VBox(layout=widgets.Layout(
                width='100%'))
            for obj in _objs:
                self._parse_config(wdg, obj)
            _evts = config.get('evts', None) or []
            for evt in _evts:
                self._parse_config(wdg, evt)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'tab':# {{{
            selected_index = config.get('selected_index', 0)
            wdg = TabE(layout=self.tab_layout)
            wdg.titles = [''] * 4
            for i, _obj in enumerate(_objs):
                box = widgets.VBox(layout=tlo)
                for obj in _obj['objs']:
                    self._parse_config(box, obj)
                _widget_add_child(wdg, box)
                wdg.set_title(i, _obj['name'] if isinstance(_obj['name'], str) else _obj['name'][self.lan])
            wdg.selected_index = selected_index
            wdg.description = _name
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'accordion':# {{{
            selected_index = config.get('selected_index', 0)
            wdg = AccordionE(layout=self.accordion_layout)
            # wdg.titles = [obj['name'][self.lan] for obj in _objs]
            for i, _obj in enumerate(_objs):
                box = widgets.VBox(layout=tlo)
                for obj in _obj['objs']:
                    self._parse_config(box, obj)
                _widget_add_child(wdg, box)
                wdg.set_title(i, _obj['name'] if isinstance(_obj['name'], str) else _obj['name'][self.lan])
            wdg.selected_index = selected_index
            wdg.description = _name
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'navigation':# {{{

            def _value_change(change):
                wdg = change['owner']
                val = change['new']
                parent_box = wdg.parent_box
                trigger_box = parent_box.boxes[val]
                parent_box.children = [parent_box.children[0], trigger_box]

            label = widgets.Label(value=_name[self.lan] if _name else ' ', layout=self.label_layout)
            btns = widgets.ToggleButtons(style={'description_width': '0px'})
            btns.description = __id_
            wdg = widgets.VBox(layout=self.nav_layout)
            wdg.node_type = 'navigation'
            wdg.boxes = []
            options = []
            for i, obj in enumerate(_objs):
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], i))
                box = widgets.VBox(layout=tlo)
                self._parse_config(box, obj)
                wdg.boxes.append(box)
            wdg.children = [widgets.HBox([label, btns]), wdg.boxes[0]]
            btns.options = options
            btns.parent_box = wdg
            btns.observe(_value_change, 'value')
            self._wid_map(__id_, btns)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'debug':  # debug {{{
            options = []
            for obj in _objs:
                options.append((obj['name'], obj['value']))
            index = config.get('index', 0)
            wdg = self.Debug(_name[self.lan], options, index)
            return _widget_add_child(widget, [wdg, self.out])
# }}}
        elif _type == 'output':  # output{{{
            # tlo.border = '1px solid gray'
            wdg = widgets.Output(layout=tlo)
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'object':# {{{
            if _name:
                wdg = widgets.HTML(value=f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            for obj in _objs:
                self._parse_config(widget, obj)
            return widget
# }}}
        elif _type == 'html':# {{{
            value = config.get('text', '<hr>')
            wdg = widgets.HTML(value=f'{value}')
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'H':# {{{
            if _name:
                wdg = widgets.HTML(value=f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            # layout.display = 'flex'
            # layout.flex_flow = 'row'
            wdg = widgets.HBox(layout=tlo)
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'V':# {{{
            if _name:
                wdg = widgets.HTML(value=f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            # layout.display = 'flex'
            # layout.flex_flow = 'column'
            wdg = widgets.VBox(layout=tlo)
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'bool':# {{{
            wdg = self.Bool(
                __id_,
                description=description,
                layout=tlo,
                style=tstyle,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'int':# {{{
            _range = config.get('range', False)
            slider = config.get('slider', False)
            wdg = self.Int(
                __id_,
                slider, _range,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'float':# {{{
            slider = config.get('slider', False)
            _range = config.get('range', False)
            wdg = self.Float(
                __id_,
                slider, _range,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'string':# {{{
            wdg = self.String(
                __id_,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'label':# {{{
            wdg = self.Label(
                __id_,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'bytes':# {{{
            wdg = self.Bytes(
                __id_,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'text':# {{{
            wdg = self.Text(
                __id_,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'image':# {{{
            plt = config.get('plt', False)
            if plt:
                wdg = self.Image(__id_, ext=True, layout=tlo, **args)
                e_onclick, e_keydown = None, None
            else:
                wdg = self.Image(__id_, ext=False, layout=tlo, **args)
                e_onclick = config.get('e_onclick', False)
                e_keydown = config.get('e_keydown', False)

            wdg.description = description
            watch_events = []
            if e_onclick:
                watch_events.append('click')
            if e_keydown:
                watch_events.append('keydown')
            if len(watch_events) > 0:
                from ipyevents import Event
                wdg._d = Event(source=wdg, watched_events=['dragstart'], prevent_default_action=True) # no drag
                wdg._e = Event(source=wdg, watched_events=watch_events)

                def _handle_events(w_image, w_show, event):
                    x, y = event['dataX'], event['dataY']
                    data = {'xy': [x, y]}
                    try:
                        if is_install_cv2 and len(w_image.value) > 0:
                            img_bgr = cv2.imdecode(np.frombuffer(w_image.value, dtype=np.uint8), cv2.IMREAD_COLOR)
                            img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
                            # img_hls = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HLS)
                            img_lab = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2LAB)
                            img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                            data['rgb'] = img_bgr[y, x][::-1].tolist()
                            data['hsv'] = img_hsv[y, x].tolist()
                            # data['hls'] = img_hls[y, x].tolist()
                            data['lab'] = img_lab[y, x].tolist()
                            data['gray'] = int(img_gray[y, x])
                        w_show.value = json.dumps(data)
                    except Exception:
                        self.logger(f'{traceback.format_exc(limit=5)}')

                label = widgets.Label(layout=widgets.Layout(
                    width=f'{width}px', border='2px solid red', justify_content='flex-start'))
                self._wid_map(f'{__id_}_event', label)
                wdg._e.on_dom_event(lambda event, w_image=wdg, w_show=label: _handle_events(w_image, w_show, event))
                wdg = widgets.VBox([label, wdg])
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'canvas':# {{{
            wdg = self.Canvas(
                __id_,
                layout=tlo,
                **args,)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'video':# {{{
            btn_snapshot = config.get('btn_snapshot')
            if btn_snapshot:
                wdg = self.Video(__id_, ext=True, layout=tlo, **args)
            else:
                wdg = self.Video(__id_, ext=False, layout=tlo, **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'int-array' or _type == 'float-array' or _type == 'string-array':# {{{
            default = config.get('default', '[]')
            wdg = self.Array(
                __id_,
                description=description,
                value=json.dumps(default),
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'string-enum':# {{{
            options = []
            boxes = []
            btn_next = config.get('btn_next')
            btn_prev = config.get('btn_prev')
            btn_delete = config.get('btn_delete')
            _options = config.get('options', [])
            for obj in _options:
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
            wdg = self.StringEnum(
                __id_,
                options=options,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args,
            )

            is_ext = btn_next or btn_prev or btn_delete
            blo = widgets.Layout(width='100px')
            if btn_prev:
                w_prev = widgets.Button(layout=blo, description='Previous', icon='arrow-left', button_style='info')
                width += 100

                def _on_previous(w_btn, w_target):
                    if w_target.index > 0:
                        w_target.index -= 1
                w_prev.on_click(lambda btn, T=wdg: _on_previous(btn, T))
                boxes.append(w_prev)

            if btn_next:
                w_next = widgets.Button(layout=blo, description='Next', icon='arrow-right', button_style='info')
                width += 100

                def _on_next(w_btn, w_target):
                    if w_target.index < (len(w_target.options) - 1):
                        w_target.index += 1
                w_next.on_click(lambda btn, T=wdg: _on_next(btn, T))
                boxes.append(w_next)

            if is_ext:
                boxes.append(wdg)

            if btn_delete:
                w_delete = widgets.Button(layout=blo, description='Delete', icon='trash', button_style='danger')
                width += 100

                def _on_delete(w_btn, w_target):
                    index = w_target.index
                    options = list(copy.copy(w_target.options))
                    options.pop(index)
                    w_target.options = options
                    if len(options) == 0:
                        return
                    w_target.index = index if index < len(options) else index - 1
                w_delete.on_click(lambda btn, T=wdg: _on_delete(btn, T))

                boxes.append(w_delete)
            if is_ext:
                wdg = widgets.HBox(children=boxes, layout=widgets.Layout(
                    width=f'{width}px', height='40px', margin='0px 0px 0px 0px',
                    align_items="stretch", justify_content='flex-start'))

            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'bool-trigger':# {{{
            _options = config.get('options', [])
            triggers = {}
            for obj in _options:
                triggers['true' if obj['value'] else 'false'] = obj['trigger']

            wdg = self.BoolTrigger(
                __id_,
                triggers,
                description=description,
                layout=tlo,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'string-enum-trigger':# {{{
            options = []
            triggers = {}
            _options = config.get('options', [])
            for obj in _options:
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
                triggers[obj['value']] = obj['trigger']
            wdg = self.StringEnumTrigger(
                __id_,
                triggers,
                options=options,
                description=description,
                layout=tlo,
                style=tstyle,
                **args,
            )
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'multiselect_simple':# {{{
            options = []
            _options = config.get('options', [])
            for obj in _options:
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
            wdg = self.SimpleMultiSelect(__id_,
                options=options,
                description=description,
                layout=tlo,
                style=tstyle,
                continuous_update=False,
                **args)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'multiselect':# {{{
            options = []
            _options = config.get('options', [])
            for obj in _options:
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
            label_widget = widgets.Label(_name[self.lan], layout=widgets.Layout(
                width=tstyle['description_width'], display="flex", justify_content='flex-end'))

            search_widget = widgets.Text(continuous_update=True,
                    layout=widgets.Layout(width=tlo.width), placeholder='Search')
            v_layout = widgets.Layout(
                overflow='auto',
                border='1px solid #9e9e9e',
                margin='2px 2px 5px 2px',
                width=tlo.width,
                height=tlo.height,
                flex_flow='column',
                display='flex'
            )
            h_layout = widgets.Layout(
                width='auto',
                height=tlo.height,
            )
            # description_width
            options_dict = {description[0]: widgets.Checkbox(
                description=description[0], value=False,
                layout=widgets.Layout(width='90%'),
                style={'description_width':'10px'}) for description in options}

            for key, val in options:
                options_dict[key]._value = val

            options_widget = widgets.VBox(list(options_dict.values()), layout=v_layout)

            multi_select_widget = widgets.HBox([label_widget, widgets.VBox([search_widget, options_widget])], layout=h_layout)
            multi_select_widget.node_type = 'multiselect'
            multi_select_widget.multi_options = options_widget
            multi_select_widget.get_value = lambda widget = multi_select_widget: [w._value for w in widget.multi_options.children if w.value]

            # dynamic modify continuous_update
            # search_widget.set_state({'continuous_update': False})
            # search_widget.send_state('continuous_update')

            def on_text_change(change):
                options_widget = change['owner'].options_widget
                options_dict = change['owner'].options_dict
                search_input = change['new']
                if search_input == '':
                    new_options = list(options_dict.values())
                else:
                    close_matches = [x for x in list(options_dict.keys()) if str.lower(search_input.strip('')) in str.lower(x)]
                    new_options = [options_dict[description] for description in close_matches]
                options_widget.children = new_options

            search_widget.options_widget = options_widget
            search_widget.options_dict = options_dict
            search_widget.observe(on_text_change, names='value')

            self._wid_map(__id_, multi_select_widget)
            return _widget_add_child(widget, multi_select_widget)
# }}}
        elif _type == 'button':# {{{
            style = config.get('style', 'success')
            icon = config.get('icon', '')
            wdg = widgets.Button(
                description=description,
                disabled=False,
                icon=icon,
                button_style=style,
                layout=tlo)
            self._wid_map(__id_, wdg)

            if __id_ in self.source_on_clicks:
                handler, targets, _H = self.source_on_clicks[__id_]
                wdg.on_click(lambda btn, H=handler, T=targets: _H(H, btn, T))
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'togglebutton':# {{{
            style = config.get('style', 'success')
            icon = config.get('icon', '')
            wdg = widgets.ToggleButton(
                description=description,
                disabled=False,
                icon=icon,
                button_style=style,
                layout=tlo)
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'togglebuttons':# {{{
            style = config.get('style', 'success')
            icons = config.get('icons', [])
            options = []
            _options = config.get('options', [])
            for obj in _options:
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
            wdg = widgets.ToggleButtons(
                    description=description,
                    options=options,
                    disabled=False,
                    button_style=style,
                    icons=icons, layout=tlo)
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'radiobuttons':# {{{
            _options = config.get('options', [])
            wdg = widgets.RadioButtons(
                    description=description,
                    options=_options,
                    **args)
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'progressbar':# {{{
            style = config.get('style', 'success')
            wdg = widgets.FloatProgress(
                value=0.0,
                description=description,
                bar_style=style,
                style=tstyle,
                layout=tlo,
                **args)
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)
# }}}
        elif _type == 'iframe':
            return

        elif _type == 'string-enum-array-trigger':
            raise RuntimeError('not impl yet')

        elif _type == 'jslink':# {{{
            for obj in _objs:
                source_id, source_trait = obj['source'].split(':')
                target_id, target_trait = obj['target'].split(':')
                widgets.jslink((self.get_widget_byid(source_id), source_trait), (self.get_widget_byid(target_id), target_trait))
# }}}
        elif _type == 'jsdlink':# {{{
            for obj in _objs:
                source_id, source_trait = obj['source'].split(':')
                target_id, target_trait = obj['target'].split(':')
                widgets.jsdlink((self.get_widget_byid(source_id), source_trait), (self.get_widget_byid(target_id), target_trait))
# }}}
        elif _type == 'interactive':# {{{
            for obj in _objs:
                handler = obj['handler']
                params  = obj['params']  # noqa
                if isinstance(handler, str):
                    if handler in self.events:
                        handler = self.events[handler]
                if not callable(handler):
                    raise RuntimeError(f'Unkown callable obj{handler}')
                params = {key: self.get_widget_byid(val) for key, val in params.items()}
                widgets.interactive(handler, **params)
# }}}
        elif _type == 'interactiveX':# {{{
            for obj in _objs:
                handler = obj['handler']
                params  = obj['params']  # noqa
                if callable(handler):
                    self.events[handler.__name__] = handler
                    handler_name = handler.__name__
                else:
                    handler = self.events[handler]

                kwargs = {}
                wdgs, vals = {}, {}
                for key, val in params.items():
                    if key.startswith('w_'):
                        kwargs[key] = val
                        wdgs[key] = self.get_widget_byid(val)
                    else:
                        w = self.get_widget_byid(val)
                        if not w:
                            raise RuntimeError(f'Cannot get widget by id [{val}]')
                        vals[key] = w.value
                        kwargs[key] = w

                handler(self, **wdgs, **vals)

                def _H(h, **kwargs):
                    wdgs, vals = {}, {}
                    try:
                        handler = self.events[h]
                        for key, val in kwargs.items():
                            if key.startswith('w_'):
                                w = self.get_widget_byid(val)
                                wdgs[key] = w
                            else:
                                vals[key] = val
                        handler(self, **wdgs, **vals)
                    except Exception:
                        self.logger(traceback.format_exc(limit=6))

                widgets.interactive(_H, h=handler_name, **kwargs)
# }}}
        elif _type == 'observe':# {{{
            for obj in _objs:
                handler, params = obj['handler'], obj['params']
                if isinstance(handler, str):
                    if handler in self.events:
                        handler = self.events[handler]
                if not callable(handler):
                    raise RuntimeError(f'Unkown callable obj{handler}')

                targets = params['targets'] if 'targets' in params else [params['target']]
                sources = params['sources'] if 'sources' in params else [params['source']]

                def _H(H, change, tgs):
                    try:
                        args = []
                        for x in tgs:
                            v = x.split(':')
                            w = self.get_widget_byid(v[0])
                            if w:
                                if len(v) > 1 and hasattr(w, v[1]):
                                    w = getattr(w, v[1])
                            args.append(w)
                        return H(self, change['owner'], change['old'], change['new'], *args)
                    except Exception:
                        self.logger(traceback.format_exc(limit=6))

                for source in sources:
                    val = 'value'
                    ss = source.split(':')
                    if len(ss) == 2:
                        source, val = ss
                    source_wdg = self.get_widget_byid(source)
                    if isinstance(source_wdg, (widgets.Tab, widgets.Accordion)):
                        val = 'selected_index'
                    source_wdg.observe(lambda change, H=handler, T=targets: _H(H, change, T), val)
# }}}
        elif _type == 'onclick':# {{{
            for obj in _objs:
                handler, params = obj['handler'], obj['params']
                if isinstance(handler, str):
                    if handler in self.events:
                        handler = self.events[handler]
                if not callable(handler):
                    raise RuntimeError(f'Unkown callable obj{handler}')

                targets = params['targets'] if 'targets' in params else [params['target']]
                sources = params['sources'] if 'sources' in params else [params['source']]

                def _H(H, btn, tgs):
                    try:
                        args = []
                        for x in tgs:
                            v = x.split(':')
                            w = self.get_widget_byid(v[0])
                            if w:
                                if hasattr(w, 'node_type') and w.node_type == 'multiselect' and v[1] == 'value':
                                    w = w.get_value()
                                else:
                                    if len(v) > 1 and hasattr(w, v[1]):
                                        w = getattr(w, v[1])
                            args.append(w)
                        return H(self, btn, *args)
                    except Exception:
                        self.logger(traceback.format_exc(limit=6))

                for source in sources:
                    source_wdg = self.get_widget_byid(source)
                    if source_wdg is not None:
                        source_wdg.on_click(lambda btn, H=handler, T=targets: _H(H, btn, T))
                    else:
                        self.source_on_clicks[source] = (handler, targets, _H)
# }}}
        elif _type == 'oncanvas':# {{{
            for obj in _objs:
                handler, params = obj['handler'], obj['params']
                if isinstance(handler, str):
                    if handler in self.events:
                        handler = self.events[handler]
                if not callable(handler):
                    raise RuntimeError(f'Unkown callable obj{handler}')

                evttype = obj['evttype']
                targets = params['targets'] if 'targets' in params else [params['target']]
                sources = params['sources'] if 'sources' in params else [params['source']]

                def _H(H, S, tgs, mx, my):
                    try:
                        args = []
                        for x in tgs:
                            v = x.split(':')
                            w = self.get_widget_byid(v[0])
                            if w:
                                if hasattr(w, 'node_type') and w.node_type == 'multiselect' and v[1] == 'value':
                                    w = w.get_value()
                                else:
                                    if len(v) > 1 and hasattr(w, v[1]):
                                        w = getattr(w, v[1])
                            args.append(w)
                        return H(self, S, mx, my, *args)
                    except Exception:
                        self.logger(traceback.format_exc(limit=6))

                for source in sources:
                    source_wdg = self.get_widget_byid(source)
                    if source_wdg is None:
                        continue
                    if evttype == 'mouse_up':
                        source_wdg.on_mouse_up(lambda x, y, S=source_wdg, H=handler, T=targets: _H(H, S, T, x, y))
# }}}
        else:
            for obj in _objs:
                self._parse_config(widget, obj)
            return widget

    def parse_schema(self, config, tooltips=False):# {{{
        if not isinstance(config, dict):
            print('config is not dict')
            return

        # add debug
        if self.debug:
            exist = False
            for obj in config['objs']:
                if obj['type'] == 'debug':
                    exist = True
                    break
            if not exist:
                config['objs'].append({
                    'type': 'debug',
                    'name': {'cn': '调试: ', 'en': 'Debug: '},
                    'index': 0,
                    'objs': [
                        {'name': 'Logger', 'value': 'logger'},
                        {'name': 'Observe', 'value': 'observe'},
                        {'name': 'Key-Value(changed)', 'value': 'kv'},
                        {'name': 'Json(changed)', 'value': 'json'},
                        {'name': 'Key-Value(all)', 'value': 'kvs'},
                        {'name': 'Json(all)', 'value': 'jsons'}
                    ]})

        self.init_page()
        box = widgets.Box(layout=self.page_layout)
        self._parse_config(box, config)
        self.page.children = [box]
        self.defaultconfg = self.get_all_kv(False)
        if tooltips:
            return _schema_tooltips(self.wid_widget_map)
# }}}


def nbeasy_schema_parse(config, lan='en', debug=True, events={}, border=False):# {{{
    if is_install_cv2:
        plt.close('all')
    g = WidgetGenerator(lan, debug=debug, events=events, border=border)
    try:
        g.parse_schema(config)
    except Exception:
        traceback.print_exc(limit=8)
    display(g.page)
    return g# }}}


##################################################################
# <codecell> Schema Type
##################################################################

def nbeasy_widget_type(id_, type_, label, default=None, tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    easy = {
        '_id_': id_,
        'type': type_,
        'name': label,
    }
    if len(label) == 0:
        easy['description_width'] = 0
    if default is not None:
        easy['default'] = default
    if width:
        easy['width'] = width
    if height:
        easy['height'] = height
    if tips:
        easy['tips'] = tips
    if readonly:
        easy['readonly'] = True
    if description_width is not None:
        easy['description_width'] = description_width
    if len(label) == 0:
        easy['description_width'] = 0
    return easy# }}}


def nbeasy_widget_hline():# {{{
    return {'type': 'html', 'text': '<hr>'}# }}}


def nbeasy_widget_output(id_, width='100%', height='auto'):# {{{
    return {'type': 'output', '_id_':id_, 'width': width, 'height': height}# }}}


def nbeasy_widget_bool(id_, label, default=False, tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'bool', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_int(id_, label, default=0, min_=None, max_=None, step=None, slider=False, # {{{
        range_=False, description_width=None, tips=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'int', label, default, tips, description_width, width, height, readonly)
    if min_ is not None:
        easy['min'] = min_
    if max_ is not None:
        easy['max'] = max_
    if step is not None:
        easy['step'] = step
    easy['slider'] = slider
    easy['range'] = range_
    return easy# }}}


def nbeasy_widget_float(id_, label, default=0.0, min_=None, max_=None, step=None, slider=False, # {{{
        range_=False, tips=None, description_width=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'float', label, default, tips, description_width, width, height, readonly)
    if min_ is not None:
        easy['min'] = min_
    if max_ is not None:
        easy['max'] = max_
    if step is not None:
        easy['step'] = step
    easy['slider'] = slider
    easy['range'] = range_
    return easy# }}}


def nbeasy_widget_string(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'string', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_label(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=True):# {{{
    return nbeasy_widget_type(id_, 'label', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_bytes(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'bytes', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_text(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'text', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_intarray(id_, label, default=[], tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'int-array', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_floatarray(id_, label, default=[], tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'float-array', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_stringarray(id_, label, default=[], tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    return nbeasy_widget_type(id_, 'string-array', label, default, tips, description_width, width, height, readonly)# }}}


def nbeasy_widget_stringenum(# {{{
        id_, label, default=0, enums=[], tips=None, description_width=None, width=300, height=None,
        readonly=False, btn_next=False, btn_prev=False, btn_delete=False):
    easy = nbeasy_widget_type(id_, 'string-enum', label, default, tips, description_width, width, height, readonly)
    if len(enums) != 0:
        easy['options'] = [{
            'name': x if isinstance(x, str) else x[0],
            'value': x if isinstance(x, str) else x[1]
        } for x in enums]
        easy['default'] = enums[default] if isinstance(enums[default], str) else enums[default][1]
    easy['btn_next'] = btn_next
    easy['btn_prev'] = btn_prev
    easy['btn_delete'] = btn_delete

    return easy# }}}


def nbeasy_widget_image(id_, label='', default='', format='url', tips=None, description_width=None,# {{{
        width=300, height=300, e_onclick=False, e_keydown=False, plt=False):
    easy = nbeasy_widget_type(id_, 'image', label, default, tips, description_width, width, height, readonly=False)
    easy['format'] = format
    easy['e_onclick'] = e_onclick
    easy['e_keydown'] = e_keydown
    easy['plt'] = plt
    return easy# }}}


def nbeasy_widget_canvas(id_, label=' ', width=300, height=300):# {{{
    easy = {
        '_id_': id_,
        'type': 'canvas',
        'name': '',
        'width': width,
        'height': height
    }
    return easy# }}}


def nbeasy_widget_video(id_, label=' ', default='', format='url', tips=None, description_width=None,# {{{
        width=None, height=None, btn_snapshot=False):
    easy = nbeasy_widget_type(id_, 'video', label, default, tips, description_width, width, height, readonly=False)
    easy['format'] = format
    easy['btn_snapshot'] = btn_snapshot
    return easy# }}}


def nbeasy_widget_booltrigger(id_, label, default=False, triggers=[], tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    easy = nbeasy_widget_type(id_, 'bool-trigger', label, default, tips, description_width, width, height, readonly)
    assert len(triggers) == 2, 'bool triggers number is must 2'
    easy['options'] = [
        {
            'name': 'Enable',
            'value': True,
            'trigger': triggers[1]
        },
        {
            'name': 'Disable',
            'value': False,
            'trigger': triggers[0]
        }
    ]
    return easy
# }}}


def nbeasy_widget_stringenumtrigger(id_, label, default=0, enums=[], triggers=[], tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    easy = nbeasy_widget_stringenum(id_, label, default, enums, tips, description_width, width, height, readonly)
    easy['type'] = 'string-enum-trigger'
    for i, trigger in enumerate(triggers):
        assert isinstance(trigger, dict), 'stringnum trigger must be dict type'
        easy['options'][i]['trigger'] = trigger
    return easy# }}}


def nbeasy_widget_button(id_, label=' ', style='success', tips=None, description_width=None, width=None, height=None, icon=''):# {{{
    easy = nbeasy_widget_type(id_, 'button', label, None, tips, description_width, width, height)
    easy['style'] = style  # ['primary', 'success', 'info', 'warning', 'danger', '']
    easy['icon'] = icon  # https://fontawesome.com/v4/icons/ FontAwesome names without the `fa-` prefix
    return easy# }}}


def nbeasy_widget_togglebutton(id_, label=' ', default=False, tips=None, description_width=None, width=None, height=None, style='success', icon=''):# {{{
    easy = nbeasy_widget_type(id_, 'togglebutton', label, default, tips, description_width, width, height)
    easy['style'] = style  # ['primary', 'success', 'info', 'warning', 'danger', '']
    easy['icon'] = icon
    return easy# }}}


def nbeasy_widget_togglebuttons(id_, label=' ', default=0, enums=[], tips=None, description_width=None, width=None, height=None, style='success', icons=[]):# {{{
    easy = nbeasy_widget_stringenum(id_, label, default, enums, tips, description_width, width, height)
    easy['type'] = 'togglebuttons'
    easy['style'] = style  # ['primary', 'success', 'info', 'warning', 'danger', '']
    easy['icons'] = icons
    return easy# }}}


def nbeasy_widget_radiobuttons(id_, label, default, enums, tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    easy = nbeasy_widget_type(id_, 'radiobuttons', label, default, tips, description_width, width, height, readonly)
    assert len(enums) > 0
    easy['options'] = enums
    easy['default'] = enums[default] if isinstance(enums[default], str) else enums[default][1]
    return easy# }}}


def nbeasy_widget_progressbar(id_, label, style='success', min_=0.0, max_=100.0, tips=None, description_width=None, width=None, height=None):# {{{
    easy = nbeasy_widget_type(id_, 'progressbar', label, None, tips, description_width, width, height, readonly=False)
    if min_ is not None:
        easy['min'] = min_
    if max_ is not None:
        easy['max'] = max_
    easy['style'] = style  # ['success', 'info', 'warning', 'danger', '']
    return easy# }}}


def nbeasy_widget_multiselect(id_, label, default=0, enums=[], tips=None, description_width=None, width=100, height=100, readonly=False):# {{{
    easy = nbeasy_widget_stringenum(id_, label, default, enums, tips, description_width, width, height, readonly)
    easy['type'] = 'multiselect'
    return easy# }}}


def nbeasy_widget_multiselect_simple(id_, label, default=0, enums=[], tips=None, description_width=None, width=None, height=None, readonly=False):# {{{
    easy = nbeasy_widget_type(id_, 'multiselect_simple', label, default, tips, description_width, width, height, readonly)
    if len(enums) == 0:
        enums = ['NONE']
    easy['options'] = [{
        'name': x if isinstance(x, str) else x[0],
        'value': x if isinstance(x, str) else x[1]
    } for x in enums]
    easy['default'] = default
    easy['type'] = 'multiselect_simple'
    return easy# }}}

## Display


def nbeasy_widget_display(images, img_wid=None, resize=(), isrgb=False, fontscale=0.5, ctx=None):# {{{
    if isinstance(images, np.ndarray):
        images = {'_': images}
    elif isinstance(images, bytes):
        images = cv2.imdecode(np.frombuffer(images, dtype=np.uint8), cv2.IMREAD_COLOR)
        images = {'_': images}
    elif isinstance(images, tuple) or isinstance(images, list):
        images = {f'_{i}': img for i, img in enumerate(images)}
    C = len(images)
    if C == 0:
        return None
    img_h, img_w = images[list(images.keys())[0]].shape[:2]
    if resize == 'auto':
        if img_w < 960:
            resize = ()
        else:
            resize = round(960 / img_w, 3)
    if isinstance(resize, float) and resize != 1.0:
        resize = (int(resize * img_w), int(resize * img_h))
    show_ncol, show_nrow = 1, 1
    if C > 1:
        if img_wid:
            if not resize:
                show_ncol = 2 if img_w < 960 else 1
            else:
                show_ncol = 2 if resize[0] < 960 else 1
        for i in range(C % show_ncol):
            images[f'placehold-{i}'] = images[list(images.keys())[-1]].copy()
        row_images = []
        col_images = []
        for key, img in images.items():
            if not key.startswith('_'):
                cv2.putText(img, key, (150, 150), cv2.FONT_HERSHEY_SIMPLEX, fontscale, (255, 6, 2), 1)
            col_images.append(img)
            if len(col_images) == show_ncol:
                row_images.append(np.hstack(col_images))
                col_images = []

        show_nrow = len(row_images)
        display_image = np.vstack(row_images)
    else:
        resize = None
        display_image = images.popitem()[1]

    isgray = 2 == len(display_image.shape)

    if img_wid:
        dh, dw = display_image.shape[:2]
        ratio = 1
        if resize:
            ww, wh = show_ncol * resize[0], show_nrow * resize[1]
            ratio = min(ww / dw, wh / dh)
        if ratio != 1:
            dw, dh = int(ratio * dw), int(ratio * dh)

        if isinstance(img_wid, ImageE):
            img_wid.layout.width = f'{dw + 50}px'
            img_wid.layout.height = f'{dh + 50}px'
            if not isrgb and not isgray:
                display_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
            img_wid.imshow(display_image, dw, dh)
        else:
            img_wid.layout.width = f'{dw}px'
            img_wid.layout.height = f'{dh}px'
            if isinstance(img_wid, widgets.Image):
                if isrgb and not isgray:
                    display_image = cv2.cvtColor(display_image, cv2.COLOR_RGB2BGR)
                img_wid.width = str(dw)
                img_wid.height = str(dh)
                img_wid.value = io.BytesIO(cv2.imencode('.png', display_image)[1]).getvalue()
            else:
                img_wid.width, img_wid.height = dw, dh
                if not isrgb:
                    display_image = cv2.cvtColor(display_image, cv2.COLOR_BGR2RGB)
                img_wid.put_image_data(display_image)
                img_wid.send_state()
    else:
        # return io.BytesIO(cv2.imencode('.png', display_image)[1]).getvalue()
        return display_image
# }}}


def nbeasy_show_image(image, width=-1, height=-1, plt=False):# {{{
    if isinstance(image, str):
        fmt, value = 'url', image
    else:
        fmt, value = 'png', io.BytesIO(cv2.imencode('.png', image)[1]).getvalue()
    widgen = nbeasy_schema_parse(
        {
            'type': 'page',
            'objs': [
                {
                    'type': 'H',
                    'objs': [
                        nbeasy_widget_image(
                            '__cfg.image',
                            'Image',
                            value,
                            format=fmt,
                            width=width, height=height,
                            e_onclick=True, plt=plt)
                    ]
                }
            ]
        }, debug=False)
    return widgen.get_widget_byid('__cfg.image')
# }}}


def nbeasy_show_video(video, width=640, height=320):# {{{
    schema = {
        'type': 'page',
        'objs': [
            {
                'type': 'H',
                'objs': [
                    {
                        'type': 'V',
                        'objs': [
                            nbeasy_widget_video('__cfg.video', 'Video', video, width=width, height=height, btn_snapshot=True),
                            nbeasy_widget_bytes('cfg.video_url_show', 'Url', video, width=width, description_width=30),
                        ],
                        'align_items': 'center',
                        'width': '50%'
                    },
                    {
                        'type': 'V',
                        'objs': [
                            nbeasy_widget_image('__cfg.image', 'Image', '', width=width, height=height, e_onclick=True),
                            nbeasy_widget_bytes('cfg.image_url_show', 'Url', '', width=width, description_width=30),
                        ],
                        'align_items': 'center',
                        'width': '50%'
                    }
                ],
                'align_items': 'flex-end', # bottom align
            }, # video and image
        ],
        'evts': [
            {
                'type': 'jsdlink',
                'objs': [
                    {
                        'source': '__cfg.video:snapshot',
                        'target': '__cfg.image:value'
                    },
                    {
                        'source': 'cfg.video_url_show:bvalue',
                        'target': '__cfg.video:value'
                    },
                    {
                        'source': 'cfg.image_url_show:bvalue',
                        'target': '__cfg.image:value'
                    },
                ]
            }, # jsdlink
        ]
    }
    widgen = nbeasy_schema_parse(schema, debug=False)
    return widgen.get_widget_byid('__cfg.video'), widgen.get_widget_byid('__cfg.image')
# }}}

## Reference

# 1. https://kapernikov.com/ipywidgets-with-matplotlib/
# 2. https://ipycanvas.readthedocs.io/en/latest/installation.html
# 3. https://matplotlib.org/ipympl/examples/full-example.html

## matplot
# %matplotlib notebook
# import numpy as np
# import matplotlib.pyplot as plt
# fig = plt.figure()
# ax = fig.add_subplot(111)
# ax.plot(np.random.rand(10))
# text=ax.text(0,0, "", va="bottom", ha="left")
#
# def onclick(event):
#     tx = 'button=%d, x=%d, y=%d, xdata=%f, ydata=%f' % (event.button, event.x, event.y, event.xdata, event.ydata)
#     print(tx)
#     text.set_text(tx)
#
# cid = fig.canvas.mpl_connect('button_press_event', onclick)
