"""R6 · Base común de los generadores de flujos .ows (requiere el Python de Orange).

Registra los widgets y ofrece BaseFlow: describir widgets, empaquetar ajustes,
enlazar nodos validando canales y guardar el .ows.
"""
import importlib
import io
import os
import pkgutil
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from AnyQt.QtWidgets import QApplication  # noqa: F401,E402

import Orange.widgets as _ow  # noqa: E402
from Orange.canvas.config import Config  # noqa: E402
from Orange.widgets.tests.base import WidgetTest  # noqa: E402
from Orange.widgets.utils.filedialogs import RecentPath  # noqa: E402
from orangecanvas.registry import WidgetRegistry, WidgetDiscovery  # noqa: E402
from orangecanvas.scheme import Scheme, SchemeNode, SchemeLink, readwrite  # noqa: E402
from orangewidget.workflow.discovery import WidgetDiscovery as _WD  # noqa: E402

W = "Orange.widgets."

# Registra las categorías de widgets de Orange.
_registro = WidgetRegistry()
_discovery = WidgetDiscovery(_registro)
_entry_point = next(iter(Config().widgets_entry_points()))
for _m in pkgutil.iter_modules(_ow.__path__):
    if _m.ispkg and _m.name not in ("tests", "utils", "report", "settings"):
        _pkg = importlib.import_module("Orange.widgets." + _m.name)
        if hasattr(_pkg, "NAME"):
            _discovery.process_category_package(_pkg, distribution=_entry_point.dist)
_DISC = _WD(WidgetRegistry())


class _H(WidgetTest):
    def runTest(self):  # noqa: D102
        pass


_H.setUpClass()
helper = _H()
helper.setUp()


def ruta(rel):
    """Ruta relativa al .ows: el flujo abre en cualquier equipo que clone el repo."""
    return RecentPath("orange/data/" + rel.rsplit("/", 1)[-1], "basedir", rel)


def stored_settings(wcls, settings):
    """Ajustes con la versión del widget, para evitar migraciones."""
    stored = dict(settings)
    stored["__version__"] = getattr(wcls, "settings_version", 1)
    return stored


def clean_file_paths(props):
    """Descarta los datasets de ejemplo que Orange guarda con rutas absolutas de este equipo."""
    props["recent_paths"] = [p for p in props.get("recent_paths", []) if getattr(p, "prefix", None) == "basedir"]
    props.pop("active_path", None)


class BaseFlow:
    def __init__(self, title, description, out):
        self.scheme = Scheme(title=title, description=description)
        self.nodes = {}
        self.out = Path(out)
        self.out.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def describe(qname):
        """(descripción, clase y nombre) del widget 'paquete.modulo.Clase'."""
        mod, _, cname = qname.rpartition(".")
        modulo = importlib.import_module(mod)
        return _DISC.widget_description(modulo, widget_name=cname), getattr(modulo, cname), cname

    @staticmethod
    def pack(w):
        """Ajustes listos para guardar, sin la geometría de la ventana."""
        props = w.settingsHandler.pack_data(w)
        props.pop("savedWidgetGeometry", None)
        return props

    def place(self, key, desc, title, pos, props):
        node = SchemeNode(desc, title=title, position=pos, properties=props)
        self.scheme.add_node(node)
        self.nodes[key] = node
        return node

    def link(self, a, out, b, inp):
        na, nb = self.nodes[a], self.nodes[b]
        outs = [c.name for c in na.description.outputs]
        ins = [c.name for c in nb.description.inputs]
        if out not in outs:
            raise ValueError(f"{a}: salida '{out}' no existe; hay {outs}")
        if inp not in ins:
            raise ValueError(f"{b}: entrada '{inp}' no existe; hay {ins}")
        self.scheme.add_link(SchemeLink(na, out, nb, inp))

    def save(self, fname):
        buf = io.BytesIO()
        readwrite.scheme_to_ows_stream(self.scheme, buf, pretty=True, pickle_fallback=True)
        p = self.out / fname
        p.write_bytes(buf.getvalue())
        print("escrito", p, len(buf.getvalue()), "bytes |", len(self.scheme.nodes), "nodos,", len(self.scheme.links), "enlaces")
