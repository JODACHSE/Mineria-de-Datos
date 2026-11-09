"""R6 · Genera el flujo 03 (texto de YouTube) con la API de Orange y el complemento Text.

Uso (con el Python de Orange 3.40 + Orange3-Text, desde la raíz del repo):
    python scripts/R6/generar_flujo_texto.py orange/flujos orange/data/youtube
Crea orange/flujos/03_comentarios_youtube.ows. Crea cada widget real, comprueba que los ajustes pedidos quedaron
aplicados, ejecuta Preprocess -> Bag of Words y fija en Select Rows la condición "video = Vxx" con datos reales.
Las rutas del flujo (corpus.csv, stopwords_es.txt) son relativas al .ows: abre en cualquier equipo que clone el repo.
"""
import io, os, sys, unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from AnyQt.QtWidgets import QApplication  # noqa

from orangecanvas.registry import WidgetRegistry, WidgetDiscovery
from orangecanvas.scheme import Scheme, SchemeNode, SchemeLink, readwrite
from Orange.canvas.config import Config
from Orange.widgets.tests.base import WidgetTest
from Orange.widgets.utils.filedialogs import RecentPath

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

reg = WidgetRegistry()
import importlib, pkgutil
import Orange.widgets as _ow
_disc = WidgetDiscovery(reg)
_ep = next(iter(Config().widgets_entry_points()))
for _m in pkgutil.iter_modules(_ow.__path__):
    if _m.ispkg and _m.name not in ("tests", "utils", "report", "settings"):
        _pkg = importlib.import_module("Orange.widgets." + _m.name)
        if hasattr(_pkg, "NAME"):
            _disc.process_category_package(_pkg, distribution=_ep.dist)
from orangewidget.workflow.discovery import WidgetDiscovery as _WD
_DISC = _WD(WidgetRegistry())
_NOMBRE = {}


class _H(WidgetTest):
    def runTest(self):  # noqa
        pass


_H.setUpClass()

helper = _H()
helper.setUp()



class Flow:
    def __init__(self, title, description):
        self.scheme = Scheme(title=title, description=description)
        self.nodes, self.w = {}, {}

    def add(self, key, qname, title, pos, feed=None, **settings):
        mod, _, cname = qname.rpartition(".")
        desc = _DISC.widget_description(importlib.import_module(mod), widget_name=cname)
        wcls = getattr(importlib.import_module(mod), cname)
        import copy
        stored = copy.deepcopy(settings)           # Orange modifica estos objetos al resolver rutas
        stored["__version__"] = getattr(wcls, "settings_version", 1)   # evita migraciones de ajustes antiguos
        env = {"basedir": str(DATOS.parent.parent / "flujos")} if cname == "OWPreprocess" else {}   # solo Preprocess necesita resolver su lista de palabras vacías
        w = helper.create_widget(wcls, stored_settings=stored, env=env)
        for k, v in settings.items():           # compara contra la copia: la migración de Orange puede mutar el dict
            if not hasattr(w, k):
                raise AttributeError(f"{cname} no tiene el ajuste '{k}'")
            if k in ("recent_paths", "storedsettings"):
                continue
            if isinstance(v, dict):
                for kk, vv in v.items():
                    if getattr(getattr(w, k), kk) != vv:
                        raise ValueError(f"{cname}.{k}.{kk}: pedí {vv!r} y quedó {getattr(getattr(w, k), kk)!r}")
            elif getattr(w, k) != v:
                raise ValueError(f"{cname}.{k}: pedí {v!r} pero quedó {getattr(w, k)!r}")
        if feed:
            feed(w)
        props = w.settingsHandler.pack_data(w)
        props.pop("savedWidgetGeometry", None)
        if cname == "OWPreprocess":
            # Se guarda lo pedido (rutas relativas al .ows), no lo que Orange resolvió con el entorno de este equipo
            props["storedsettings"] = settings["storedsettings"]
        if cname == "OWFile":
            props["recent_paths"] = [p for p in props.get("recent_paths", []) if getattr(p, "prefix", None) == "basedir"]
            props.pop("active_path", None)
        node = SchemeNode(desc, title=title, position=pos, properties=props)
        self.scheme.add_node(node)
        self.nodes[key], self.w[key] = node, w
        return w

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
        p = OUT / fname
        p.write_bytes(buf.getvalue())
        print("escrito", p, len(buf.getvalue()), "bytes |", len(self.scheme.nodes), "nodos,", len(self.scheme.links), "enlaces")


def ruta(rel):
    # Ruta relativa al .ows (prefix 'basedir'); abspath es solo un marcador neutro, sin rutas personales
    return RecentPath("orange/data/" + rel.rsplit("/", 1)[-1], "basedir", rel)


W = "Orange.widgets."
T = "orangecontrib.text.widgets."
DATOS = Path(sys.argv[2]).resolve()                    # carpeta orange/data/youtube con corpus.csv
RUTA_SW = ruta("../data/youtube/stopwords_es.txt")
K_TEMAS = 4
PP = {"name": "", "preprocessors": [
    ("preprocess.transform", {"methods": [0, 3]}),                         # minúsculas + quitar URL
    ("preprocess.tokenize", {"method": 3, "pattern": r"\w+"}),             # palabras
    ("preprocess.filter", {                                                # ANTES de normalizar: si no, las raíces no coinciden con la lista
        "methods": [0, 2, 3, 4], "language": None, "sw_path": RUTA_SW, "sw_list": [RUTA_SW],
        "lx_path": None, "lx_list": [], "incl_num": False, "pattern": r"^.{1,2}$",
        "freq_type": 1, "abs_start": 2, "abs_end": 1000000}),              # palabras en >= 2 comentarios
    ("preprocess.normalize", {"method": 1, "snowball_language": "es", "lemmagen_language": "es"}),   # Snowball español
]}

# Para fijar la condición "video = Vxx" en Select Rows hay que abrir su contexto con los datos reales
from Orange.data import Table  # noqa
from orangecontrib.text.widgets.owcorpus import OWCorpus  # noqa

h = Flow("R6 · Comentarios de YouTube · análisis de texto",
         "Comentarios limpios (corpus.csv) -> preprocesamiento en español -> temas (LDA), palabras que distinguen cada video "
         "(Word Enrichment) y colocaciones.")
f_file = h.add("file", W + "data.owfile.OWFile", "Comentarios (corpus.csv)", (60, 240),
               recent_paths=[ruta("../data/youtube/corpus.csv")])
tabla = Table.from_file(str(DATOS / "corpus.csv"))
f_corpus = h.add("corpus", T + "owcorpus.OWCorpus", "Corpus", (220, 240))
helper.send_signal(f_corpus.Inputs.data, tabla, widget=f_corpus)
corpus = helper.get_output(f_corpus.Outputs.corpus, widget=f_corpus)
f_pre = h.add("pre", T + "owpreprocess.OWPreprocess", "Preprocesar texto (español)", (380, 240), storedsettings=PP)
helper.send_signal(f_pre.Inputs.corpus, corpus, widget=f_pre)
helper.wait_until_finished(widget=f_pre, timeout=60000)
tokens = helper.get_output(f_pre.Outputs.corpus, widget=f_pre)
f_bow = h.add("bow", T + "owbagofwords.OWTBagOfWords", "Bolsa de palabras (conteo)", (560, 240))
helper.send_signal(f_bow.Inputs.corpus, tokens, widget=f_bow)
helper.wait_until_finished(widget=f_bow, timeout=60000)
bow = helper.get_output(f_bow.Outputs.corpus, widget=f_bow)
print('tokens', type(tokens), 'bow', type(bow), f_bow.Error.active, f_bow.Warning.active)

h.add("viewer", T + "owcorpusviewer.OWCorpusViewer", "Leer comentarios", (220, 360))
h.add("cloud", T + "owwordcloud.OWWordCloud", "Nube de palabras", (560, 60))
h.add("col", T + "owcollocations.OWCollocations", "Colocaciones (bigramas)", (560, 140), freq_filter=2)
h.add("tm", T + "owtopicmodeling.OWTopicModeling", f"Temas (LDA, {K_TEMAS})", (720, 80), method_index=0, lda={"num_topics": K_TEMAS})
h.add("tm_tab", W + "data.owtable.OWTable", "Pesos de tema por comentario", (900, 80))
h.add("bow_tab", W + "data.owtable.OWTable", "Matriz documento-término", (720, 240))

videos = bow.domain["video"].values


def fijar(idx):
    def _f(w):
        helper.send_signal(w.Inputs.data, bow, widget=w)
        w.remove_all_rows()
        w.add_row(bow.domain["video"], 0, (idx + 1,))               # discreto: operador 0 = "is", valor = (índice + 1,)
        w.conditions_changed()
        assert w.conditions and getattr(w.conditions[0][0], "name", w.conditions[0][0]) == "video", w.conditions
    return _f


for i, v in enumerate(videos):
    cod = v[:3]
    y = 360 + 110 * i
    sr = h.add(f"sel{i}", W + "data.owselectrows.OWSelectRows", f"Solo {cod}", (720, y), feed=fijar(i))
    out = helper.get_output(sr.Outputs.matching_data, widget=sr)
    assert out is not None and len(out) > 0, f"Select Rows {cod} sin filas"
    h.add(f"enr{i}", T + "owwordenrichment.OWWordEnrichment", f"Palabras que distinguen a {cod}", (900, y))

h.link("file", "Data", "corpus", "Data")
h.link("corpus", "Corpus", "viewer", "Corpus")
h.link("corpus", "Corpus", "pre", "Corpus")
h.link("pre", "Corpus", "bow", "Corpus")
h.link("pre", "Corpus", "cloud", "Corpus")
h.link("pre", "Corpus", "col", "Corpus")
h.link("pre", "Corpus", "tm", "Corpus")
h.link("tm", "Corpus", "tm_tab", "Data")
h.link("bow", "Corpus", "bow_tab", "Data")
for i in range(len(videos)):
    h.link("bow", "Corpus", f"sel{i}", "Data")
    h.link("bow", "Corpus", f"enr{i}", "Data")
    h.link(f"sel{i}", "Matching Data", f"enr{i}", "Selected Data")
h.save("03_comentarios_youtube.ows")
