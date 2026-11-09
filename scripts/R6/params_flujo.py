"""Parámetros únicos de los modelos: los usan el generador de .ows y la validación headless."""
LR = dict()                                   # Regresión logística: Ridge (L2), C = 1 (valores por defecto de Orange)
TREE = dict(binary_trees=False,               # sin binarización exhaustiva: Departamento tiene 32 valores (límite 16)
            limit_depth=True, max_depth=12,   # poda previa para limitar el sobreajuste
            limit_min_internal=True, min_internal=50,
            limit_min_leaf=True, min_leaf=20)
RF = dict(n_estimators=100, use_min_samples_split=True, min_samples_split=5,
          use_max_depth=False, use_random_state=True)   # Random Forest: 100 árboles, semilla fija
