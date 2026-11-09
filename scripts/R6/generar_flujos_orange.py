"""Genera los flujos .ows de R6 con la API de Orange (valida widgets y canales contra el registro real).

Uso:  QT_QPA_PLATFORM=offscreen python3 build_ows.py <carpeta_salida>
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


def fqn(name):
    return name


class Flow:
    def __init__(self, title, description):
        self.scheme = Scheme(title=title, description=description)
        self.nodes = {}

    def add(self, key, qname, title, pos, **settings):
        import importlib as _il
        desc = _DISC.widget_description(_il.import_module(qname.rpartition('.')[0]), widget_name=qname.rpartition('.')[2])
        desc.name = _NOMBRE.get(qname, desc.name)
        cls = desc.widget_class if hasattr(desc, "widget_class") else None
        # Instancia el widget real para validar los nombres de ajustes y empaquetar valores
        import importlib
        mod, _, cname = qname.rpartition(".")
        wcls = getattr(importlib.import_module(mod), cname)
        pedido = dict(settings)                     # copia: la migración de Orange puede mutar el dict original
        stored = dict(settings)
        stored["__version__"] = getattr(wcls, "settings_version", 1)   # evita migraciones de ajustes antiguos
        w = helper.create_widget(wcls, stored_settings=stored)
        for k, v in pedido.items():
            if not hasattr(w, k):
                raise AttributeError(f"{cname} no tiene el ajuste '{k}'")
            if k != "recent_paths" and getattr(w, k) != v:
                raise ValueError(f"{cname}.{k}: pedí {v!r} pero quedó {getattr(w, k)!r}")
        props = w.settingsHandler.pack_data(w)
        props.pop("savedWidgetGeometry", None)
        if qname.endswith("OWFile"):
            # Orange añade datasets de ejemplo con rutas absolutas de ESTE equipo: se descartan.
            # Queda solo la ruta relativa al .ows (resuelta en cualquier equipo que clone el repo).
            props["recent_paths"] = [p for p in props.get("recent_paths", []) if getattr(p, "prefix", None) == "basedir"]
            props.pop("active_path", None)
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
        p = OUT / fname
        p.write_bytes(buf.getvalue())
        print("escrito", p, len(buf.getvalue()), "bytes |", len(self.scheme.nodes), "nodos,", len(self.scheme.links), "enlaces")


def archivo(rel):
    # Ruta relativa al .ows (prefix 'basedir'): el flujo abre en cualquier equipo que clone el repo.
    # abspath es solo un marcador neutro (sin rutas personales); Orange resuelve con prefix+relpath
    return [RecentPath("orange/data/" + rel.rsplit("/", 1)[-1], "basedir", rel)]


from params_flujo import LR, TREE, RF
W = "Orange.widgets."

# ======================================================================
# Flujo 1 · Supervisado: tres modelos, mismas condiciones de evaluación
# ======================================================================
f = Flow("R6 · Supervisado · ¿Rendimiento alto o bajo?",
         "Tres modelos (regresión logística, árbol, Random Forest) sobre eva_supervisado.csv. "
         "Clase: RendimientoAlto (Alto = rendimiento sobre la mediana 2019-2023 de su cultivo).")
f.add("file", W + "data.owfile.OWFile", "EVA supervisado", (60, 220), recent_paths=archivo("../data/eva_supervisado.csv"))
f.add("tabla", W + "data.owtable.OWTable", "Datos", (60, 340))
f.add("dist", W + "visualize.owdistributions.OWDistributions", "Balance de clases", (60, 100))
f.add("cols", W + "data.owselectcolumns.OWSelectAttributes", "Variables (sin fuga)", (230, 220))
f.add("rank", W + "data.owrank.OWRank", "Relevancia de variables", (230, 340))
f.add("lr", W + "model.owlogisticregression.OWLogisticRegression", "Regresión logística", (420, 100), **LR)
f.add("tree", W + "model.owtree.OWTreeLearner", "Árbol", (420, 220), **TREE)
f.add("rf", W + "model.owrandomforest.OWRandomForest", "Random Forest", (420, 340), **RF)
f.add("file_tr", W + "data.owfile.OWFile", "Entrenamiento 2019-2023", (230, 500),
      recent_paths=archivo("../data/eva_supervisado_entrenamiento_2019_2023.csv"))
f.add("file_te", W + "data.owfile.OWFile", "Prueba 2024", (230, 620),
      recent_paths=archivo("../data/eva_supervisado_prueba_2024.csv"))
f.add("ts_cv", W + "evaluate.owtestandscore.OWTestAndScore", "Test and Score · CV (estratificada / por municipio)", (640, 220),
      resampling=0, n_folds=3, cv_stratified=True)   # 10 pliegues estratificados; cambiar a "por variable" -> GrupoCV
f.add("ts_t", W + "evaluate.owtestandscore.OWTestAndScore", "Test and Score · temporal 2024", (640, 500), resampling=5)  # Test on test data
f.add("cm_cv", W + "evaluate.owconfusionmatrix.OWConfusionMatrix", "Matriz de confusión · CV", (850, 160))
f.add("roc_cv", W + "evaluate.owrocanalysis.OWROCAnalysis", "ROC · CV", (850, 280))
f.add("cm_t", W + "evaluate.owconfusionmatrix.OWConfusionMatrix", "Matriz de confusión · 2024", (850, 500))

f.link("file", "Data", "tabla", "Data")
f.link("file", "Data", "dist", "Data")
f.link("file", "Data", "cols", "Data")
f.link("cols", "Data", "rank", "Data")
f.link("cols", "Data", "ts_cv", "Data")
f.link("file_tr", "Data", "ts_t", "Data")
f.link("file_te", "Data", "ts_t", "Test Data")
for lr in ("lr", "tree", "rf"):
    f.link(lr, "Learner", "ts_cv", "Learner")
    f.link(lr, "Learner", "ts_t", "Learner")
f.link("ts_cv", "Evaluation Results", "cm_cv", "Evaluation Results")
f.link("ts_cv", "Evaluation Results", "roc_cv", "Evaluation Results")
f.link("ts_t", "Evaluation Results", "cm_t", "Evaluation Results")
f.save("01_supervisado.ows")

# ======================================================================
# Flujo 2 · Clustering de municipios
# ======================================================================
g = Flow("R6 · Clustering de municipios",
         "k-Means sobre eva_municipios.csv (tamaño, mezcla de cultivos, diversificación, tasa de cosecha). "
         "El rendimiento NO entra al agrupamiento: se usa después para caracterizar los grupos.")
g.add("file", W + "data.owfile.OWFile", "EVA municipios", (60, 220), recent_paths=archivo("../data/eva_municipios.csv"))
g.add("tabla", W + "data.owtable.OWTable", "Datos", (60, 340))
g.add("km", W + "unsupervised.owkmeans.OWKMeans", "k-Means (k de 2 a 10, estandariza)", (260, 220),
      optimize_k=True, k_from=2, k_to=10, normalize=True, smart_init=0, n_init=10, max_iterations=300)
g.add("sil", W + "visualize.owsilhouetteplot.OWSilhouettePlot", "Silhouette", (470, 100))
g.add("box", W + "visualize.owboxplot.OWBoxPlot", "Perfil de cada grupo", (470, 220))
g.add("mosaic", W + "visualize.owmosaic.OWMosaicDisplay", "Grupo × Región", (470, 340))
g.add("tab_c", W + "data.owtable.OWTable", "Municipios con grupo", (470, 460))
g.link("file", "Data", "tabla", "Data")
g.link("file", "Data", "km", "Data")
g.link("km", "Data", "sil", "Data")
g.link("km", "Data", "box", "Data")
g.link("km", "Data", "mosaic", "Data")
g.link("km", "Data", "tab_c", "Data")
g.save("02_clustering.ows")
