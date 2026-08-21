# 📊 Minería de Datos - Aplicación Web & Dashboard

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask_3.0-green.svg)](https://flask.palletsprojects.com/)
[![Bootstrap](https://img.shields.io/badge/UI-Bootstrap_5.3-7952B3.svg)](https://getbootstrap.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](#)

Proyecto web modular desarrollado en **Flask** enfocado en la enseñanza, exploración y despliegue de conceptos, metodologías y modelos analíticos de **Minería de Datos**.

---

## 🚀 Descripción del Proyecto

Esta aplicación actúa como una plataforma integral para organizar las lecciones del curso y presentar los avances del proyecto final de analítica. Su objetivo principal es integrar un proceso completo de datos para extraer conocimientos evidentes, multidimensionales, ocultos y profundos mediante técnicas descriptivas y predictivas.

---

## 🛠️ Stack Tecnológico

* **Backend / Web:** Python, Flask 3.x
* **Frontend:** Jinja2, HTML5, CSS3, Bootstrap 5.3 & Bootstrap Icons
* **Procesamiento & Analítica:** Apache Spark (Spark ML), Orange, Clustering
* **Visualización / BI:** Power BI
* **Entorno & Herramientas:** Git, GitHub, VS Code, `python-dotenv`

---

## 📁 Estructura del Repositorio

```text
└── 📁Mineria de Datos
    ├── 📁app
    │   ├── 📁components
    │   ├── 📁routes
    │   │   ├── lessons.py        # Rutas de las lecciones del curso
    │   │   └── project.py        # Rutas del módulo del proyecto
    │   ├── 📁static
    │   │   ├── 📁css
    │   │   │   └── styles.css
    │   │   └── 📁js
    │   │       └── index.js
    │   ├── 📁templates
    │   │   ├── 📁layouts
    │   │   │   └── base.html     # Plantilla base con Bootstrap 5.3 e Iconos
    │   │   ├── 📁lessons
    │   │   │   ├── index.html
    │   │   │   └── clase_01.html # Apuntes estructurados de la Clase 1
    │   │   └── 📁project
    │   │       └── index.html
    │   ├── __init__.py           # Application Factory (create_app)
    │   └── config.py             # Configuración general de Flask
    ├── 📁tests
    ├── .env.example              # Plantilla de variables de entorno
    ├── .gitignore
    ├── README.md
    ├── requirements.txt          # Dependencias de Python
    └── run.py                    # Punto de entrada de la aplicación