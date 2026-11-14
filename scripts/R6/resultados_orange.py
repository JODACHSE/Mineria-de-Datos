"""R6 · Reproduce sin interfaz los resultados de los flujos 01 y 02 y los guarda para la app.

Usa la librería de Orange con los mismos parámetros que los widgets (params_flujo.py):
métricas de los tres modelos en las tres evaluaciones, matrices de confusión, silueta
por k y perfil de los grupos de k-Means. Escribe app/static/data/R6/resultados.json,
que lee la sección «Conocimiento oculto» de Flask.

Uso (con el Python que trae Orange 3.40):
    "%LOCALAPPDATA%/Programs/Orange/python.exe" scripts/R6/resultados_orange.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import confusion_matrix, silhouette_samples

import Orange
from Orange.classification import LogisticRegressionLearner, RandomForestLearner, TreeLearner
from Orange.evaluation import AUC, CA, F1, Precision, Recall
from Orange.evaluation import CrossValidation, CrossValidationFeature, TestOnTestData
from Orange.preprocess import Normalize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from params_flujo import LR, RF, TREE  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "orange" / "data"
OUT = ROOT / "app" / "static" / "data" / "R6" / "resultados.json"


def learners():
    # Traducción de los ajustes de los widgets (params_flujo.py) a los learners de la librería.
    return [
        ("Regresión logística", LogisticRegressionLearner(**LR)),
        ("Árbol", TreeLearner(binarize=TREE["binary_trees"], max_depth=TREE["max_depth"],
                              min_samples_split=TREE["min_internal"], min_samples_leaf=TREE["min_leaf"])),
        ("Random Forest", RandomForestLearner(n_estimators=RF["n_estimators"],
                                              min_samples_split=RF["min_samples_split"], random_state=0)),
    ]


def resumen(res, nombres, target):
    labels = list(res.domain.class_var.values)
    out = []
    auc, ca = AUC(res), CA(res)
    f1, pr, rc = (m(res, target=target) for m in (F1, Precision, Recall))
    for i, nombre in enumerate(nombres):
        cm = confusion_matrix(res.actual, res.predicted[i], labels=range(len(labels)))
        out.append({"modelo": nombre, "auc": round(float(auc[i]), 3), "ca": round(float(ca[i]), 3),
                    "f1": round(float(f1[i]), 3), "precision": round(float(pr[i]), 3),
                    "recall": round(float(rc[i]), 3),
                    "matriz": {"etiquetas": labels, "valores": cm.tolist()}})
    return out


def supervisado():
    data = Orange.data.Table(str(DATA / "eva_supervisado.csv"))
    train = Orange.data.Table(str(DATA / "eva_supervisado_entrenamiento_2019_2023.csv"))
    test = Orange.data.Table(str(DATA / "eva_supervisado_prueba_2024.csv"))
    target = list(data.domain.class_var.values).index("Alto")
    nombres = [n for n, _ in learners()]
    grupo = data.domain["GrupoCV"]

    evals = {
        "cv": ("Validación cruzada estratificada (10 pliegues)",
               CrossValidation(k=10, stratified=True, random_state=0)(data, [l for _, l in learners()])),
        "municipio": ("Validación cruzada por municipio (GrupoCV)",
                      CrossValidationFeature(feature=grupo)(data, [l for _, l in learners()])),
        "temporal": ("Entrenar 2019–2023 → probar 2024",
                     TestOnTestData()(train, test, [l for _, l in learners()])),
    }
    clase = Counter(data.domain.class_var.str_val(v) for v in data.Y)
    return {
        "registros": len(data), "entrenamiento": len(train), "prueba": len(test),
        "clase": dict(clase), "pct_alto": round(100 * clase["Alto"] / len(data), 1),
        "predictoras": [a.name for a in data.domain.attributes],
        "evaluaciones": {k: {"nombre": n, "modelos": resumen(r, nombres, target)} for k, (n, r) in evals.items()},
    }


def _nombre_grupo(perfil):
    cultivos = sorted(((v, c) for c, v in perfil["pct_area"].items()), reverse=True)
    v1, c1 = cultivos[0]
    if v1 >= 60:
        base = f"Especializados en {c1.lower()}"
    else:
        base = f"Mixtos de {c1.lower()} y {cultivos[1][1].lower()}"
    return base


def clustering():
    data = Orange.data.Table(str(DATA / "eva_municipios.csv"))
    norm = Normalize(norm_type=Normalize.NormalizeBySD, center=True)(data)  # «Normalize columns» del widget
    X = norm.X
    silhouettes, modelos = {}, {}
    for k in range(2, 11):
        km = Orange.clustering.KMeans(n_clusters=k, init="k-means++", n_init=10, max_iter=300, random_state=0)
        model = km.get_model(norm)
        labels = np.asarray(model.labels)
        s = silhouette_samples(X, labels)
        silhouettes[k] = round(float(s.mean()), 3)
        modelos[k] = (labels, s)
    k = max(silhouettes, key=silhouettes.get)
    labels, s = modelos[k]

    names = [a.name for a in data.domain.attributes]
    metas = {m.name: data.get_column(m.name) for m in data.domain.metas}
    cultivos = [n.replace("PctArea_", "") for n in names if n.startswith("PctArea_")]
    perfiles = []
    for g in range(k):
        idx = labels == g
        col = lambda n: data.get_column(n)[idx]  # noqa: E731
        region_var = data.domain["Region"]
        regiones = Counter(region_var.str_val(v) for v in metas["Region"][idx])
        perfil = {
            "municipios": int(idx.sum()),
            "pct_area": {c: round(float(col(f"PctArea_{c}").mean()), 1) for c in cultivos},
            "area_anual_ha_geo": round(float(10 ** col("Log10_AreaSembradaAnual").mean())),
            "num_cultivos": round(float(col("NumCultivos").mean()), 1),
            "diversificacion": round(float(col("Diversificacion").mean()), 2),
            "tasa_cosecha": round(float(col("TasaCosecha").mean()), 2),
            "rend_rel_mediana": round(float(np.median(data.get_column("RendRelMediano_posteriori")[idx])), 2),
            "regiones": {r: round(100 * n / idx.sum()) for r, n in regiones.most_common(3)},
            "silueta": round(float(s[idx].mean()), 3),
            "pct_silueta_negativa": round(float(100 * (s[idx] < 0).mean())),
        }
        perfil["nombre"] = _nombre_grupo(perfil)
        perfiles.append(perfil)
    # Orden estable para la app: por cultivo dominante, no por el índice interno de k-Means.
    perfiles.sort(key=lambda p: max(p["pct_area"], key=p["pct_area"].get))
    for i, p in enumerate(perfiles, start=1):
        p["grupo"] = f"G{i}"
    return {"municipios": len(data), "variables": names, "k_elegido": k,
            "silueta_por_k": silhouettes, "silueta_global": silhouettes[k], "grupos": perfiles}


def main():
    out = {"orange_version": Orange.version.version, "supervisado": supervisado(), "clustering": clustering()}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Escrito {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
