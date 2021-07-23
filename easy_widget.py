#!/usr/bin/python3
# -*- coding: utf-8 -*-

# @file easy_widget.py
# @brief
# @author QRS
# @blog qrsforever.github.io
# @version 1.0
# @date 2019-12-18 19:55:57

from IPython.display import display, clear_output
from traitlets.utils.bunch import Bunch
import traitlets
import ipywidgets  as widgets
import base64
import os
import json
import pprint
import traceback
from pyhocon import ConfigFactory
from pyhocon import HOCONConverter

widgets.Dropdown.value.tag(sync=True)

def _schema_tooltips(widget_map):
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

def observe_widget(method):
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


class BytesText(widgets.Text):
    bvalue = traitlets.CBytes(help="Bytes value").tag(sync=True)


class WidgetGenerator():
    def __init__(self, lan = 'en', debug=False, events=None, border=False):
        self.page = widgets.Box()
        self.out = widgets.Output(layout={'border': '1px solid black', 'width': '100%', 'height':'auto'})
        self.output_type = 'none'
        self.lan = lan
        self.tag = 'tag'
        self.debug = debug
        self.border = border
        self.events = events
        self.dataset_dir = ''
        self.dataset_url = ''
        self.basic_types = ['int', 'float', 'bool',
                'string', 'int-array', 'float-array',
                'string-array', 'string-enum', 'image']

        self.vlo = widgets.Layout(
                width='auto',
                align_items='stretch',
                justify_content='flex-start',
                margin='3px 0px 3px 0px',
                )
        if self.border:
            self.vlo.border = 'solid 2px red'

        self.hlo = widgets.Layout(
                width='100%',
                flex_flow='row wrap',
                align_items='stretch',
                justify_content='flex-start',
                margin='3px 0px 3px 0px',
                )
        if self.border:
            self.hlo.border = 'solid 2px blue'

        self.page_layout = widgets.Layout(
                display='flex',
                width='100%',
                )
        if self.border:
            self.page_layout.border = 'solid 2px black'

        self.tab_layout = widgets.Layout(
                display='flex',
                width='99%',
                )
        if self.border:
            self.tab_layout.border = 'solid 2px yellow'

        self.accordion_layout = widgets.Layout(
                display='flex',
                width='99%',
                )
        if self.border:
            self.accordion_layout.border = 'solid 2px green'

        self.nav_layout = widgets.Layout(
                display='flex',
                width='99%',
                margin='3px 0px 3px 0px',
                border='1px solid black',
                )

        self.btn_layout = widgets.Layout(
                margin='3px 0px 3px 0px',
                )

        self.label_layout = widgets.Layout(
                width="60px",
                justify_content="center",
                )

    def init_page(self):
        self.wid_widget_map = {}
        self.wid_value_map = {}

    def get_widget_byid(self, wid):
        if wid in self.wid_widget_map:
            return self.wid_widget_map[wid]
        return None

    def get_all_kv(self):
        kv_map = {}

        def _get_kv(widget):
            if isinstance(widget, widgets.Box):
                if hasattr(widget, 'node_type') and widget.node_type == 'navigation':
                    for child in widget.boxes:
                        _get_kv(child)
                else:
                    for child in widget.children:
                        _get_kv(child)
            else:
                if hasattr(widget, 'id') and widget.id[0] != '_' and hasattr(widget, 'value'):
                    value = widget.value
                    if isinstance(value, bytes):
                        value = value.decode()
                    if hasattr(widget, 'switch_value'):
                        kv_map[widget.id] = widget.switch_value(value)
                    else:
                        kv_map[widget.id] = value

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

    @observe_widget
    def Debug(self, description, options):
        label = widgets.Label(value=description, layout=self.label_layout)
        wdg = widgets.ToggleButtons(
                options=options,
                # description=description,
                disabled=False,
                button_style='warning')
        wdg.parent_box = widgets.HBox(children=(label, wdg))

        def _value_change(change):
            self.output_type = change['new']

        self.output_type = options[0][1]
        return wdg, _value_change

    def _wid_map(self, wid, widget):
        widget.id = wid
        self.wid_widget_map[wid] = widget

    def _rm_sub_wid(self, widget):
        if isinstance(widget, widgets.Box):
            for child in widget.children:
                self._rm_sub_wid(child)
        else:
            if hasattr(widget, 'id'):
                if widget.id in self.wid_value_map.keys():
                    del self.wid_value_map[widget.id]

    @observe_widget
    def Bool(self, wid, *args, **kwargs):
        wdg = widgets.Checkbox(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change

    @observe_widget
    def Int(self, wid, *args, **kwargs):
        wdg = widgets.BoundedIntText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass

        return wdg, _value_change

    @observe_widget
    def Float(self, wid, *args, **kwargs):
        wdg = widgets.BoundedFloatText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @observe_widget
    def String(self, wid, *args, **kwargs):
        wdg = widgets.Text(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @observe_widget
    def Bytes(self, wid, *args, **kwargs):
        wdg = BytesText(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            change['owner'].bvalue = change['new'].encode('utf-8')
        return wdg, _value_change

    @observe_widget
    def Text(self, wid, *args, **kwargs):
        wdg = widgets.Textarea(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @observe_widget
    def Array(self, wid, *args, **kwargs):
        wdg = widgets.Text(*args, **kwargs)
        self._wid_map(wid, wdg)
        wdg.switch_value = lambda val: json.loads(val)

        def _value_change(change):
            wdg = change['owner']
            val = change['new']
            self.wid_value_map[wdg.id] = wdg.switch_value(val)
        return wdg, _value_change

    @observe_widget
    def StringEnum(self, wid, *args, **kwargs):
        wdg = widgets.Dropdown(*args, **kwargs)
        self._wid_map(wid, wdg)

        def _value_change(change):
            pass
        return wdg, _value_change

    @observe_widget
    def BoolTrigger(self, wid, *args, **kwargs):
        wdg = widgets.Checkbox(*args, **kwargs)
        self._wid_map(wid, wdg)
        parent_box = widgets.VBox(layout = self.vlo)
        parent_box.trigger_box = {
                'true': widgets.VBox(layout = self.vlo),
                'false': widgets.VBox(layout = self.vlo)}
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

    @observe_widget
    def StringEnumTrigger(self, wid, *args, **kwargs):
        wdg = widgets.Dropdown(*args, **kwargs)
        self._wid_map(wid, wdg)
        parent_box = widgets.VBox(layout = self.vlo)
        parent_box.trigger_box = {value: widgets.VBox(layout = self.vlo) for _, value in wdg.options}
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

    def Video(self, wid, *args, **kwargs):
        wdg = widgets.Video(loop=False, autoplay=False, *args, **kwargs)
        self._wid_map(wid, wdg)
        return wdg

    def _parse_config(self, widget, config):
        __id_ = config.get('_id_', None) or ''
        _name = config.get('name', None)
        _type = config.get('type', None)
        _objs = config.get('objs', None) or {}

        if isinstance(_name, str):
            _name = {'en': _name, 'cn': _name}

        tlo = widgets.Layout()
        flex = config.get('flex', '0 1 auto')
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
                tlo.height = height

        tstyle = {}
        description_width = config.get('description_width', 130)
        if isinstance(description_width, str):
            tstyle['description_width'] = description_width # 45% or 'initial'
        else:
            tstyle['description_width'] = '%dpx' % description_width

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

        if _type in ['int', 'float', 'progressbar']:
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
        elif _type in ['image', 'audio', 'video']:
            if width > 0:
                args['width'] = width
            if height > 0:
                args['height'] = height
            format = config.get('format', None)
            if format:
                args['format'] = format
        elif _type in ['H', 'V']:
            tlo.align_items = config.get('align_items', 'stretch')
            tlo.justify_content = config.get('justify_content', 'flex-start')
            tlo.align_content = config.get('align_content', 'flex-start')
            tlo.margin = config.get('margin', '3px 0px 3px 0px')
            if not width:
                tlo.width = '100%'
            if self.border:
                tlo.border = '1px solid cyan'

        if _type == 'page':
            wdg = widgets.VBox(layout=widgets.Layout(
                width='100%'))
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'tab':
            wdg = widgets.Tab(layout = self.tab_layout)
            # wdg.titles = [obj['name'][self.lan] for obj in _objs]
            for i, obj in enumerate(_objs):
                wdg.set_title(i, obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan])
                box = widgets.VBox(layout = tlo)
                for obj in obj['objs']:
                    self._parse_config(box, obj)
                _widget_add_child(wdg, box)
            wdg.selected_index = 0
            return _widget_add_child(widget, wdg)

        elif _type == 'accordion':
            wdg = widgets.Accordion(layout = self.accordion_layout)
            # wdg.titles = [obj['name'][self.lan] for obj in _objs]
            for i, obj in enumerate(_objs):
                wdg.set_title(i, obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan])
                box = widgets.VBox(layout = tlo)
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

            label = widgets.Label(value= _name[self.lan] if _name else 'TODO', layout=self.label_layout)
            btns = widgets.ToggleButtons()
            wdg = widgets.VBox(layout = self.nav_layout)
            wdg.node_type = 'navigation'
            wdg.boxes = []
            options = []
            for i, obj in enumerate(_objs):
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], i))
                box = widgets.VBox(layout = tlo)
                self._parse_config(box, obj)
                wdg.boxes.append(box)
            wdg.children = [widgets.HBox([label, btns]), wdg.boxes[0]]
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
                wdg = widgets.HTML(value = f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            for obj in _objs:
                self._parse_config(widget, obj)
            return widget

        elif _type == 'H':
            if _name:
                wdg = widgets.HTML(value = f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            # layout.display = 'flex'
            # layout.flex_flow = 'row'
            wdg = widgets.HBox(layout=tlo)
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'V':
            if _name:
                wdg = widgets.HTML(value = f"<b><font color='black'>{_name[self.lan]} :</b>")
                _widget_add_child(widget, wdg)
            # layout.display = 'flex'
            # layout.flex_flow = 'column'
            wdg = widgets.VBox(layout=tlo)
            for obj in _objs:
                self._parse_config(wdg, obj)
            return _widget_add_child(widget, wdg)

        elif _type == 'bool':
            wdg = self.Bool(
                    __id_,
                    description = _name[self.lan],
                    layout = tlo,
                    style = tstyle,
                    **args
                    )
            return _widget_add_child(widget, wdg)

        elif _type == 'int':
            wdg = self.Int(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'float':
            wdg = self.Float(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'string':
            wdg = self.String(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'bytes':
            wdg = self.Bytes(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'text':
            wdg = self.Text(
                __id_,
                description = _name[self.lan],
                layout = tlo,
                style = tstyle,
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
                wdg = widgets.Image(value=fp.read(), width=width, height=height)
            # wdg = widgets.HTML(value=f'<img src={self.dataset_url}{value} title="{_name[self.lan]}" width={width} height={height}>')
            return _widget_add_child(widget, wdg)

        elif _type == 'video':
            wdg = self.Video(
                    __id_,
                    layout = tlo,
                    **args,)
            return _widget_add_child(widget, wdg)

        elif _type == 'int-array' or _type == 'float-array' or _type == 'string-array':
            default = config.get('default', '[]')
            wdg = self.Array(
                __id_,
                description = _name[self.lan],
                value = json.dumps(default),
                layout = tlo,
                style = tstyle,
                continuous_update=False,
                **args,
            )
            return _widget_add_child(widget, wdg)

        elif _type == 'string-enum':
            options = []
            for obj in _objs:
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
            wdg = self.StringEnum(
                __id_,
                options = options,
                description = _name[self.lan],
                layout = tlo,
                style = tstyle,
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
                options.append((obj['name'] if isinstance(obj['name'], str) else obj['name'][self.lan], obj['value']))
            wdg = self.StringEnumTrigger(
                __id_,
                options=options,
                description=_name[self.lan],
                layout = tlo,
                style = tstyle,
                **args,
            )
            for obj in _objs:
                self._parse_config(wdg.trigger_box[obj['value']], obj['trigger'])
            return _widget_add_child(widget, wdg)

        elif _type == 'button':
            style = config.get('style', 'success')
            wdg = widgets.Button(
                    description=_name[self.lan],
                    disabled=False,
                    button_style=style,
                    layout=tlo)
            self._wid_map(__id_, wdg)
            wdg.context = self
            return _widget_add_child(widget, wdg)

        elif _type == 'progressbar':
            style = config.get('style', 'success')
            wdg = widgets.FloatProgress(
                    value=0.0,
                    description=_name[self.lan],
                    bar_style=style,
                    layout=tlo,
                    **args)
            self._wid_map(__id_, wdg)
            return _widget_add_child(widget, wdg)

        elif _type == 'iframe':
            return

        elif _type == 'string-enum-array-trigger':
            raise RuntimeError('not impl yet')

        elif _type == 'jslink':
            for obj in _objs:
                source_id, source_trait =  obj['source']
                target_id, target_trait =  obj['target']
                widgets.jslink((self.get_widget_byid(source_id), source_trait), (self.get_widget_byid(target_id), target_trait))

        elif _type == 'jsdlink':
            for obj in _objs:
                source_id, source_trait =  obj['source']
                target_id, target_trait =  obj['target']
                widgets.jsdlink((self.get_widget_byid(source_id), source_trait), (self.get_widget_byid(target_id), target_trait))

        elif _type == 'interactive':
            if self.events:
                for obj in _objs:
                    handler = obj['handler']
                    params  = obj['params']
                    if handler not in self.events:
                        continue
                    handler = self.events[handler]
                    params = {key: self.get_widget_byid(val) for key, val in params.items()}
                    widgets.interactive(handler, **params)

        elif _type == 'observe':
            if self.events:
                for obj in _objs:
                    handler = obj['handler']
                    params  = obj['params']
                    if handler not in self.events:
                        continue
                    handler = self.events[handler]
                    source_wdg = self.get_widget_byid(params['source'])
                    target_wdg = self.get_widget_byid(params['target'])
                    source_wdg.observe(lambda change, H=handler, T=target_wdg: H(
                        change['owner'], change['old'], change['new'], T), 'value')

        elif _type == 'onclick':
            if self.events:
                for obj in _objs:
                    handler = obj['handler']
                    params  = obj['params']
                    if handler not in self.events:
                        continue
                    handler = self.events[handler]
                    source_wdg = self.get_widget_byid(params['source'])
                    targets = [self.get_widget_byid(x) for x in params['targets']]
                    source_wdg.on_click(lambda btn, H=handler, args=targets: H(btn, *args))

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
            exist = False
            for obj in config['objs']:
                if obj['type'] == 'output':
                    exist = True
                    break
            if not exist:
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
        box = widgets.Box(layout=self.page_layout)
        self._parse_config(box, config)
        self.page.children = [box]
        if tooltips:
            return _schema_tooltips(self.wid_widget_map)


def nbeasy_schema_parse(config, lan='en', debug=True, events=None, border=False):
    g = WidgetGenerator(lan, debug=debug, events=events, border=border)
    try:
        g.parse_schema(config)
    except Exception:
        traceback.print_exc(limit=6)
    display(g.page)
    return g


##################################################################
# <codecell> Schema Type
##################################################################

def nbeasy_widget_type(id_, type_, label, default=None, tips=None, description_width=None, width=None, height=None, readonly=False):
    easy = {
        '_id_': id_,
        'type': type_,
        'name': label,
    }
    if default:
        easy['default'] = default
    if width:
        easy['width'] = width
    if height:
        easy['height'] = height
    if tips:
        easy['tips'] = tips
    if readonly:
        easy['readonly'] = True
    if description_width:
        easy['description_width'] = description_width
    if len(label) == 0:
        easy['description_width'] = 0
    return easy

def nbeasy_widget_bool(id_, label, default=False, tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'bool', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_int(id_, label, default=0, min_=None, max_=None, description_width=None, tips=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'int', label, default, tips, description_width, width, height, readonly)
    if min_ is not None:
        easy['min'] = min_
    if max_ is not None:
        easy['max'] = max_
    return easy

def nbeasy_widget_float(id_, label, default=0.0, min_=None, max_=None, tips=None, description_width=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'float', label, default, tips, description_width, width, height, readonly)
    if min_ is not None:
        easy['min'] = min_
    if max_ is not None:
        easy['max'] = max_
    return easy

def nbeasy_widget_string(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'string', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_bytes(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'bytes', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_text(id_, label, default='', tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'text', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_intarray(id_, label, default=[], tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'int-array', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_floatarray(id_, label, default=[], tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'float-array', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_stringarray(id_, label, default=[], tips=None, description_width=None, width=None, height=None, readonly=False):
    return nbeasy_widget_type(id_, 'string-array', label, default, tips, description_width, width, height, readonly)

def nbeasy_widget_stringenum(id_, label, default=0, enums=[], tips=None, description_width=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'string-enum', label, default, tips, description_width, width, height, readonly)
    if len(enums) == 0:
        enums = ['NONE']
    easy['objs'] = [{
            'name': x if isinstance(x, str) else x[0],
            'value': x if isinstance(x, str) else x[1]
        } for x in enums]
    easy['default'] = enums[default] if isinstance(enums[default], str) else enums[default][1]
    return easy

def nbeasy_widget_image(id_, label, default='', tips=None, description_width=None, width=None, height=None):
    return nbeasy_widget_type(id_, 'image', label, default, tips, width, height, readonly=False)

def nbeasy_widget_video(id_, label, default='', format='url', tips=None, description_width=None, width=None, height=None):
    easy = nbeasy_widget_type(id_, 'video', label, default, tips, description_width, width, height, readonly=False)
    easy['format'] = format
    return easy

def nbeasy_widget_booltrigger(id_, label, default=False, triggers=[], tips=None, description_width=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'bool-trigger', label, default, tips, description_width, width, height, readonly)
    assert len(triggers) == 2, 'bool triggers number is must 2'
    easy['objs'] = [
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

def nbeasy_widget_stringenumtrigger(id_, label, default=0, enums=[], triggers=[], tips=None, description_width=None, width=None, height=None, readonly=False):
    easy = nbeasy_widget_type(id_, 'string-enum-trigger', label, default, tips, description_width, width, height, readonly)
    if len(enums) == 0:
        enums = ['NONE']
    easy['objs'] = [{
            'name': x if isinstance(x, str) else x[0],
            'value': x if isinstance(x, str) else x[1]
        } for x in enums]
    easy['default'] = enums[default] if isinstance(enums[default], str) else enums[default][1]
    for i, trigger in enumerate(triggers):
        assert isinstance(trigger, dict), 'stringnum trigger must be dict type'
        easy['objs'][i]['trigger'] = trigger
    return easy

def nbeasy_widget_button(id_, label, style='success', tips=None, description_width=None, width=None, height=None):
    easy = nbeasy_widget_type(id_, 'button', label, tips, description_width, width, height)
    easy['style'] = style # ['primary', 'success', 'info', 'warning', 'danger', '']
    return easy

def nbeasy_widget_progressbar(id_, label, style='success', min_=0.0, max_=100.0, tips=None, description_width=None, width=None, height=None):
    easy = nbeasy_widget_type(id_, 'progressbar', label, None, tips, description_width, width, height, readonly=False)
    if min_ is not None:
        easy['min'] = min_
    if max_ is not None:
        easy['max'] = max_
    easy['style'] = style # ['success', 'info', 'warning', 'danger', '']
    return easy
