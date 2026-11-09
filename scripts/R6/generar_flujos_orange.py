"""Genera los flujos .ows de R6 con la API de Orange (valida widgets y canales contra el registro real).

Uso:  QT_QPA_PLATFORM=offscreen python3 generar_flujos_orange.py <carpeta_salida>
"""
import sys

from _orange_base import BaseFlow, W, clean_file_paths, helper, ruta, stored_settings

OUT = sys.argv[1]


class Flow(BaseFlow):
    def __init__(self, title, description):
        super().__init__(title, description, OUT)

    def add(self, key, qname, title, pos, **settings):
        desc, wcls, cname = self.describe(qname)
        # Instancia el widget real para validar los nombres de ajustes y empaquetar valores
        pedido = dict(settings)                     # copia: la migración de Orange puede mutar el dict original
        w = helper.create_widget(wcls, stored_settings=stored_settings(wcls, settings))
        for k, v in pedido.items():
            if not hasattr(w, k):
                raise AttributeError(f"{cname} no tiene el ajuste '{k}'")
            if k != "recent_paths" and getattr(w, k) != v:
                raise ValueError(f"{cname}.{k}: pedí {v!r} pero quedó {getattr(w, k)!r}")
        props = self.pack(w)
        if cname == "OWFile":
            clean_file_paths(props)
        return self.place(key, desc, title, pos, props)


def archivo(rel):
    return [ruta(rel)]

from params_flujo import LR, TREE, RF

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
