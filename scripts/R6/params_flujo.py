"""R6 · Parámetros de los modelos, compartidos por el generador de .ows y resultados_orange.py."""
LR = dict()  # Regresión logística: Ridge (L2), C = 1.
TREE = dict(binary_trees=False,  # Sin binarización: Departamento tiene 32 valores (límite de Orange: 16).
            limit_depth=True, max_depth=12,  # Poda previa para limitar el sobreajuste.
            limit_min_internal=True, min_internal=50,
            limit_min_leaf=True, min_leaf=20)
RF = dict(n_estimators=100, use_min_samples_split=True, min_samples_split=5,
          use_max_depth=False, use_random_state=True)  # Random Forest: 100 árboles, semilla fija.
