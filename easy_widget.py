#!/usr/bin/python3
# -*- coding: utf-8 -*-

# @file easy_widget.py
# @brief
# @author QRS
# @blog qrsforever.github.io
# @version 1.0
# @date 2019-12-18 19:55:57

from IPython.display import display, clear_output
from ipywidgets import (HTML, Text, BoundedIntText, Output, Textarea, FloatProgress, # noqa
                        BoundedFloatText, Box, HBox, VBox, Dropdown, Button, FileUpload,
                        Image, Layout, Tab, Accordion, ToggleButtons, Checkbox, Label)

from traitlets.utils.bunch import Bunch
import base64
import os
import json
import pprint
from pyhocon import ConfigFactory
from pyhocon import HOCONConverter


def _schema_tooltips(widget_map):
    tables = []
    for key, wid in widget_map.items():
        if not hasattr(wid, 'description_tooltip') \
                or wid.description_tooltip is None \
                or wid.disabled:
            continue

        if isinstance(wid, Text):
            if wid.value.startswith('[') and wid.value.endswith(']'):
                value = json.loads(wid.value)
                if isinstance(value[0], int):
                    tables.append((key, wid.description, '整型数组', wid.value, '[int, int, ...]', wid.description_tooltip))
                elif isinstance(value[0], float):
                    tables.append((key, wid.description, '浮点数组', wid.value, '[float, float, ...]', wid.description_tooltip))
            else:
                tables.append((key, wid.description, '字符串', wid.value, '', wid.description_tooltip))
        elif isinstance(wid, BoundedIntText):
            tables.append((key,
                           wid.description,
                           '整型',
                           wid.value,
                           f'{"(-inf" if wid.min == -2147483647 else "[%d" % wid.min}, {"+inf)" if wid.max == 2147483647 else "%d]" % wid.max}',
                           wid.description_tooltip))
        elif isinstance(wid, BoundedFloatText):
            tables.append((key,
                           wid.description,
                           '浮点型',
                           wid.value,
                           f'{"(-inf" if wid.min == -2147483647.0 else "[%f" % wid.min}, {"+inf)" if wid.max == 2147483647.0 else "%f]" % wid.max}',
                           wid.description_tooltip))
        elif isinstance(wid, Checkbox):
            tables.append((key,
                           wid.description,
                           '布尔型',
                           wid.value,
                           '',
                           wid.description_tooltip))
        elif isinstance(wid, Dropdown):
            for opt in wid.options:
                if opt[1] == wid.value:
                    value = opt[0]
            tables.append((key,
                           wid.description,
                           '枚举型',
                            value,
                           f'{[o[0] for o in wid.options]}',
                           wid.description_tooltip))
    return tables


def _widget_add_child(widget, wdgs):
    if not isinstance(wdgs, list):
        wdgs = [wdgs]
    for child in wdgs:
        widget.children = list(widget.children) + [child]
    return widget

def k12widget(method):
    def _widget(self, *args, **kwargs):
        wdg, cb = method(self, *args, **kwargs)
        if self.border:
            wdg.layout.border = '1px solid yellow'

        def _on_value_change(change, cb):
            wdg = change['owner']
            val = change['new']
            if hasattr(wdg, 'id'):
                self.wid_value_map[wdg.id] = val
            if cb:
                cb(change)
            self._output(change)
        wdg.observe(lambda change, cb = cb: _on_value_change(change, cb), 'value')
        return wdg.parent_box if hasattr(wdg, 'parent_box') else wdg
    return _widget


class K12WidgetGenerator():
    def __init__(self, lan = 'en', debug=False, events=None):
        self.page = Box()
        self.out = Output(layout={'border': '1px solid black', 'width': '100%', 'height':'auto'})
        self.output_type = 'none'
        self.lan = lan
        self.tag = 'tag'
        self.debug = debug
        self.border = False
        self.events = events
        self.dataset_dir = ''
        self.dataset_url = ''
        self.basic_types = ['int', 'float', 'bool',
                'string', 'int-array', 'float-array',
                'string-array', 'string-enum', 'image']

        self.style = {
                'description_width': '130px', # 45% or 'initial'
                }

        self.vlo = Layout(
                width='auto',
                align_items='stretch',
                justify_content='flex-start',
                margin='3px 0px 3px 0px',
                )
        if self.border:
            self.vlo.border = 'solid 2px red'

        self.hlo = Layout(
                width='100%',
                flex_flow='row wrap',
                align_items='stretch',
                justify_content='flex-start',
                margin='3px 0px 3px 0px',
                )
        if self.border:
            self.hlo.border = 'solid 2px blue'

        self.page_layout = Layout(
                display='flex',
                width='100%',
                )
        if self.border:
            self.page_layout.border = 'solid 2px black'

        self.tab_layout = Layout(
                display='flex',
                width='99%',
                )
        if self.border:
            self.tab_layout.border = 'solid 2px yellow'

        self.accordion_layout = Layout(
                display='flex',
                width='99%',
                )
        if self.border:
            self.accordion_layout.border = 'solid 2px green'

        self.nav_layout = Layout(
                display='flex',
                width='99%',
                margin='3px 0px 3px 0px',
                border='1px solid black',
                )

        self.btn_layout = Layout(
                margin='3px 0px 3px 0px',
                )

        self.label_layout = Layout(
                width="60px",
                justify_content="center",
                )

    def init_page(self):
        self.wid_widget_map = {}
        self.wid_value_map = {}

    def get_all_kv(self):
        kv_map = {}

        def _get_kv(widget):
            if isinstance(widget, Box):
                if hasattr(widget, 'node_type') and widget.node_type == 'navigation':
                    for child in widget.boxes:
                        _get_kv(child)
                else:
                    for child in widget.children:
                        _get_kv(child)
            else:
                if hasattr(widget, 'id') and hasattr(widget, 'value'):
                    if hasattr(widget, 'switch_value'):
                        kv_map[widget.id] = widget.switch_value(widget.value)
                    else:
                        kv_map[widget.id] = widget.value

        _get_kv(self.page)
        return kv_map

    def get_all_json(self):
        config = ConfigFactory.from_dict(self.get_all_kv())
        return json.loads(HOCONConverter.convert(config, 'json'))

    def _output(self, body, clear=1):
        if self.output_type == 'none':
            return
        with self.out:
            if clear:
                clear_output()
            if self.output_type == 'print':
                if isinstance(body, Bunch):
                    pprint.pprint(body)
                elif isinstance(body, dict):
                    print(json.dumps(body, indent=4, ensure_ascii=False))
                else:
                    print(body)
            elif self.output_type == 'kv':
                pprint.pprint(self.wid_value_map)
            elif self.output_type == 'json':
                config = ConfigFactory.from_dict(self.wid_value_map)
                print(HOCONConverter.convert(config, 'json'))
            elif self.output_type == 'kvs':
                pprint.pprint(self.get_all_kv())
            elif self.output_type == 'jsons':
                pprint.pprint(self.get_all_json())

    @k12widget
    def Debug(self, description, options):
        label = Label(value=description, layout=self.label_layout)
        wdg = ToggleButtons(
                options=options,
                # description=description,
                disabled=False,
                button_style='warning')
        wdg.parent_box = HBox(children=(label, wdg))

        def _value_change(change):
            self.output_type = change['new']

        self.output_type = options[0][1]
        return wdg, _value_change

    def _wid_map(self, wid, widget):
        widget.id = wid
        self.wid_widget_map[wid] = widget

    def _rm_sub_wid(self, widget):
        if isinstance(widget, Box):
            for child in widget.children:
                self._rm_sub_wid(child)
        else:
            if hasattr(widget, 'id'):
                if widget.id in self.wid_value_map.keys():
                    del self.wid_value_map[widget.id]

    @k12widget
    def Bool(self, wid, *args, **kwargs):
        wdg = Checkbox(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change

    @k12widget
    def Int(self, wid, *args, **kwargs):
        wdg = BoundedIntText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change

    @k12widget
    def Float(self, wid, *args, **kwargs):
        wdg = BoundedFloatText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @k12widget
    def String(self, wid, *args, **kwargs):
        wdg = Text(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @k12widget
    def Text(self, wid, *args, **kwargs):
        wdg = Textarea(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @k12widget
    def Array(self, wid, *args, **kwargs):
        wdg = Text(*args, **kwargs)
        self._wid_map(wid, wdg)
        wdg.switch_value = lambda val: json.loads(val)

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            self.wid_value_map[wdg.id] = wdg.switch_value(val)
        return wdg, _value_change

    @k12widget
    def StringEnum(self, wid, *args, **kwargs):
        wdg = Dropdown(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @k12widget
    def BoolTrigger(self, wid, *args, **kwargs):
        wdg = Checkbox(*args, **kwargs)
        self._wid_map(wid, wdg)
        parent_box = VBox(layout = self.vlo)
        parent_box.trigger_box = {
                'true': VBox(layout = self.vlo),
                'false': VBox(layout = self.vlo)}
        parent_box.layout.margin = '3px 0px 6px 0px'
        wdg.parent_box = parent_box

        def _update_layout(wdg, val):
            if val:
                trigger_box = wdg.parent_box.trigger_box['true']
                wdg.parent_box.children = [wdg, trigger_box]
                self._rm_sub_wid(wdg.parent_box.trigger_box['false'])
            else:
                trigger_box = wdg.parent_box.trigger_box['false']
                wdg.parent_box.children = [wdg, trigger_box]
                self._rm_sub_wid(wdg.parent_box.trigger_box['true'])

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            _update_layout(wdg, val)
        _update_layout(wdg, wdg.value)
        return wdg, _value_change

    @k12widget
    def StringEnumTrigger(self, wid, *args, **kwargs):
        wdg = Dropdown(*args, **kwargs)
        self._wid_map(wid, wdg)
        parent_box = VBox(layout = self.vlo)
        parent_box.trigger_box = {value: VBox(layout = self.vlo) for _, value in wdg.options}
        wdg.parent_box = parent_box

        def _update_layout(wdg, val, old):
            trigger_box = wdg.parent_box.trigger_box[val]
            wdg.parent_box.children = [wdg, trigger_box]
            if old:
                self._rm_sub_wid(wdg.parent_box.trigger_box[old])

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            old = change['old']
            _update_layout(wdg, val, old)
        _update_layout(wdg, wdg.value, None)
        return wdg, _value_change

    def _parse_config(self, widget, config):
        __id_ = config.get('_id_', None) or ''
        _name = config.get('name', None)
        _type = config.get('type', None)
        _objs = config.get('objs', None) or {}

        tlo = Layout()
        width = config.get('width', -1)
        height = config.get('height', -1)
        if width > 0:
            tlo.width = '%dpx' % width
        else:
            tlo.max_width = '280px'
        if height > 0:
            tlo.height = '%dpx' % height

        args = {}
        readonly = config.get('readonly', False)
        if readonly:
            args['disabled'] = True
        if _type in ['bool', 'int', 'float', 'string', 'text', 'string-enum',
                'bool-trigger', 'string-enum-trigger']:
            default = config.get('default', None)
            if default:
                args['value'] = default
        tips = config.get('tips', None)
        if tips:
            args['description_tooltip'] = tips

        if _type in ['int', 'float']:
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

        if _type == 'page':
            wdg = VBox(layout=Layout(
                width='100%'))
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'tab':
            wdg = Tab(layout = self.tab_layout)
            # wdg.titles = [obj['name'][self.lan] for obj in _objs]
            for i, obj in enumerate(_objs):
                wdg.set_title(i, obj['name'][self.lan])
                box = VBox(layout = self.vlo)
                for obj in obj['objs']:
                    self._parse_config(box, obj)
                _widget_add_child(wdg, box)
            wdg.selected_index = 0
            return _widget_add_child(widget, wdg)

        elif _type == 'accordion':
            wdg = Accordion(layout = self.accordion_layout)
            # wdg.titles = [obj['name'][self.lan] for obj in _objs]
            for i, obj in enumerate(_objs):
                wdg.set_title(i, obj['name'][self.lan])
                box = VBox(layout = self.vlo)
                for obj in obj['objs']:
                    self._parse_config(box, obj)
                _widget_add_child(wdg, box)
            # wdg.selected_index = 0
            return _widget_add_child(widget, wdg)

        elif _type == 'navigation':

            def _value_change(change):
                wdg = change['owner']
                val = change['new']
                parent_box = wdg.parent_box
                trigger_box = parent_box.boxes[val]
                parent_box.children = [parent_box.children[0], trigger_box]

            label = Label(value= _name[self.lan] if _name else 'TODO', layout=self.label_layout)
            btns = ToggleButtons()
            wdg = VBox(layout = self.nav_layout)
            wdg.node_type = 'navigation'
            wdg.boxes = []
            options = []
            for i, obj in enumerate(_objs):
                options.append((obj['name'][self.lan], i))
                box = VBox(layout = self.vlo)
                self._parse_config(box, obj)
                wdg.boxes.append(box)
            wdg.children = [HBox([label, btns]), wdg.boxes[0]]
            btns.options = options
            btns.parent_box = wdg
            btns.observe(_value_change, 'value')
            return _widget_add_child(widget, wdg)

        elif _type == 'output': # debug info
            options = []
            for obj in _objs:
                options.append((obj['name'], obj['value']))
            wdg = self.Debug(_name[self.lan], options)
            return _widget_add_child(widget, [wdg, self.out])

        elif _type == 'object':
            if _name:
                wdg = HTML(value = f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            for obj in _objs:
                self._parse_config(widget, obj)
            return widget

        elif _type == 'H':
            if _name:
                wdg = HTML(value = f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            wdg = HBox(layout = self.hlo)
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'V':
            if _name:
                wdg = HTML(value = f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            wdg = VBox(layout = self.vlo)
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'bool':
            wdg = self.Bool(
                    __id_,
                    description = _name[self.lan],
                    layout = tlo,
                    style = self.style,
                    **args
                    )
            return _widget_add_child(widget, wdg)

        elif _type == 'int':
            wdg = self.Int(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = self.style,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'float':
            wdg = self.Float(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = self.style,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'string':
            wdg = self.String(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = self.style,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'text':
            wdg = self.Text(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = self.style,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'image':
            value = config.get('default', None)
            width = config.get('width', '100')
            height = config.get('height', '100')
            if not value:
                raise RuntimeError('not set value')
            image_file = f'/data{value}'
            if not os.path.exists(image_file):
                return widget
            with open(image_file, 'rb') as fp:
                wdg = Image(value=fp.read(), width=width, height=height)
            # wdg = HTML(value=f'<img src={self.dataset_url}{value} title="{_name[self.lan]}" width={width} height={height}>')
            return _widget_add_child(widget, wdg)

        elif _type == 'int-array' or _type == 'float-array' or _type == 'string-array':
            default = config.get('default', '[]')
            wdg = self.Array(
                __id_,
                description = _name[self.lan],
                value = json.dumps(default),
                layout = tlo,
                style = self.style,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'string-enum':
            options = []
            for obj in _objs:
                options.append((obj['name'][self.lan], obj['value']))
            wdg = self.StringEnum(
                __id_,
                options = options,
                description = _name[self.lan],
                layout = tlo,
                style = self.style,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'bool-trigger':
            wdg = self.BoolTrigger(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                **args,
                )
            for obj in _objs:
                trigger_obj = obj['trigger']
                trigger_box = wdg.trigger_box['true' if obj['value'] else 'false']
                self._parse_config(trigger_box, trigger_obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'string-enum-trigger':
            options = []
            for obj in _objs:
                options.append((obj['name'][self.lan], obj['value']))
            wdg = self.StringEnumTrigger(
                __id_,
                options = options,
                description = _name[self.lan],
                layout = tlo,
                style = self.style,
                **args,
            )
            for obj in _objs:
                self._parse_config(wdg.trigger_box[obj['value']], obj['trigger'])
            return _widget_add_child(widget, wdg)

        elif _type == 'button':
            if self.events is None:
                return
            wdg = Button(
                    description=_name[self.lan],
                    disabled=False,
                    button_style='danger',
                    layout=Layout(margin='5px 0px 25px 145px'))
            wdg.context = self
            wdg.on_click(self.events['project.confirm'])
            return _widget_add_child(widget, wdg)

        elif _type == 'iframe':
            return

        elif _type == 'string-enum-array-trigger':
            raise RuntimeError('not impl yet')

        else:
            for obj in _objs:
                self._parse_config(widget, obj)
            return widget

    def parse_schema(self, config, tooltips=False):
        if not isinstance(config, dict):
            print('config is not dict')
            return

        # add debug
        if self.debug:
            config['objs'].append({
                'type': 'output',
                'name': {'cn': '调试: ', 'en': 'Debug: '},
                'objs': [
                    {'name': 'Print', 'value': 'print'},
                    {'name': 'Key-Value(changed)', 'value': 'kv'},
                    {'name': 'Json(changed)', 'value': 'json'},
                    {'name': 'Key-Value(all)', 'value': 'kvs'},
                    {'name': 'Json(all)', 'value': 'jsons'}
                ]})

        self.init_page()
        box = Box(layout=self.page_layout)
        self._parse_config(box, config)
        self.page.children = [box]
        if tooltips:
            return _schema_tooltips(self.wid_widget_map)


def erlangai_schema_parse(config, lan='en', debug=True):
    g = WidgetGenerator(lan, debug=debug)
    g.parse_schema(config)
    display(g.page)
    return g
