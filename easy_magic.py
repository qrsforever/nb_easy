#!/usr/bin/env python3
#
# @file easy_magic.py
# @brief
# @author QRS
# @version 1.0
# @date 2024-03-23 14:27

import os
import json
import random
import urllib

from IPython.core.magic import register_line_magic
from IPython.core.magic import register_cell_magic


#################################################################################
### generate_toc
#################################################################################
# {{{
def _get_notebook_filepath():
    from ipykernel import get_connection_file  # type: ignore
    connection_file = get_connection_file()
    with open(connection_file, 'r') as f:
        jdata = json.load(f)
    return jdata['jupyter_session']

@register_line_magic
def generate_toc(notebook_path):
    if len(notebook_path) == 0:
        notebook_path = _get_notebook_filepath()
    indent_char="&emsp;"

    def is_markdown(it):
        return "markdown" == it["cell_type"]

    with open(notebook_path, 'r') as in_f:
        nb_json = json.load(in_f)

    is_first_title, level_adj = True, 0
    toc_numbers, toc_str = [], []
    for cell in filter(is_markdown, nb_json["cells"]):
        for source in cell["source"]:
            line = source.strip()
            if not line.startswith("#"):
                continue
            title = line.lstrip("#").lstrip()
            level = line.count("#")
            if is_first_title:
                if level > 1:
                    level_adj = level - 1
                is_first_title = False
            level -= level_adj
            if level > len(toc_numbers):
                toc_numbers.append(1)
            else:
                toc_numbers[level - 1] += 1
                toc_numbers[level:] = [1] * (len(toc_numbers) - level)

            toc_number_str = ".".join(str(num) for num in toc_numbers[:level])
            indent = indent_char * level
            url = urllib.parse.quote(title.replace(" ", "-"))
            out_line = f"{indent}{toc_number_str} [{title}](#{url})<br>\n"
            toc_str.append(out_line)

    from IPython import display
    display.display(display.Markdown(''.join(toc_str)))
# }}}


#################################################################################
### start_netron
#################################################################################
# {{{
def _open_port(port, height=600):
    from IPython import display
    from html import escape as html_escape
    frame_id = 'erlangai-frame-{:08x}'.format(random.getrandbits(64))
    body = '''
      <iframe id='%HTML_ID%' width='100%' height='%HEIGHT%' frameborder='0'>
      </iframe>
      <script>
        (function() {
          const frame = document.getElementById(%JSON_ID%);
          const url = new URL(%URL%, window.location);
          const port = %PORT%;
          if (port) {
            url.port = port;
          }
          frame.src = url;
        })();
      </script>
    '''
    replacements = [
        ('%HTML_ID%', html_escape(frame_id, quote=True)),
        ('%JSON_ID%', json.dumps(frame_id)),
        ('%HEIGHT%', '%d' % height),
        ('%PORT%', '%d' % port),
        ('%URL%', json.dumps('/')),
    ]
    for (k, v) in replacements:
        body = body.replace(k, v)
    display.display(display.HTML(body))


@register_line_magic
def start_netron(line):
    # Use: %netron /path/to/model.onnx 8601 600
    # port: 8600 - 8630
    args = line.split()
    file, port, height = args[0], int(args[1]), 600
    if len(args) == 3:
        height = int(args[2])
    import netron  # type: ignore
    from IPython import display
    netron.stop(port)
    # only support http
    netron.start(file, address=('0.0.0.0', port), browse=False)
    try:
        # support multiple sessions
        _open_port(port, height)
    except Exception:
        # only one session
        display.display(display.IFrame(f"http://localhost:{port}", width='100%', height=height))
# }}}


#################################################################################
### format_writefile
#################################################################################
# {{{
@register_cell_magic
def format_writefile(line, cell):
    path = os.path.dirname(line)
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    with open(line, 'w') as fw:
        fw.write(cell.format(**globals()))
# }}}
