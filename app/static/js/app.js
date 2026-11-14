/** app.js — punto de entrada: inicializa cada módulo (los que no encuentran sus elementos no hacen nada). */
import { initSound } from "./core/sound.js";
import { initTheme } from "./core/theme.js";
import { initLayout } from "./core/layout.js";
import { initMotion } from "./core/motion.js";
import { initExplorer } from "./features/explorer.js";
import { initCharts } from "./features/charts.js";
import { initOlap } from "./etapas/r5/olap.js";
import { initR6Charts } from "./etapas/r6/charts.js";
import { initRoadmap } from "./features/roadmap.js";

initLayout();
initSound();
initTheme();
initMotion();
initExplorer();
initCharts();
initOlap();
initR6Charts();
initRoadmap();
