"""R6 · Genera el flujo 03 (texto de YouTube) con la API de Orange y el complemento Text.

Uso (con el Python de Orange 3.40 + Orange3-Text, desde la raíz del repo):
    python scripts/R6/generar_flujo_texto.py orange/flujos orange/data/youtube
Crea orange/flujos/03_comentarios_youtube.ows. Crea cada widget real, comprueba que los ajustes pedidos quedaron
aplicados, ejecuta Preprocess -> Bag of Words y fija en Select Rows la condición "video = Vxx" con datos reales.
Las rutas del flujo (corpus.csv, stopwords_es.txt) son relativas al .ows: abre en cualquier equipo que clone el repo.
"""
import copy
import sys
from pathlib import Path

from _orange_base import BaseFlow, W, clean_file_paths, helper, ruta, stored_settings

OUT = sys.argv[1]


class Flow(BaseFlow):
    def __init__(self, title, description):
        super().__init__(title, description, OUT)
        self.w = {}

    def add(self, key, qname, title, pos, feed=None, **settings):
        desc, wcls, cname = self.describe(qname)
        stored = stored_settings(wcls, copy.deepcopy(settings))   # Orange modifica estos objetos al resolver rutas
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
        props = self.pack(w)
        if cname == "OWPreprocess":
            # Se guarda lo pedido (rutas relativas al .ows), no lo que Orange resolvió con el entorno de este equipo
            props["storedsettings"] = settings["storedsettings"]
        if cname == "OWFile":
            clean_file_paths(props)
        self.place(key, desc, title, pos, props)
        self.w[key] = w
        return w

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
