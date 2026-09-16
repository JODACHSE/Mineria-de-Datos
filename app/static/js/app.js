/**
 * app.js — punto de entrada. Cada módulo es autónomo y se activa solo si
 * encuentra sus elementos en la página.
 */
import { initSound } from "./modules/sound.js";
import { initTheme } from "./modules/theme.js";
import { initMotion } from "./modules/motion.js";
import { initExplorer } from "./modules/explorer.js";
import { initCharts } from "./modules/charts.js";

initSound();
initTheme();
initMotion();
initExplorer();
initCharts();
