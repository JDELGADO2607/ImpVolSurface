# Estado de Continuación y Hoja de Ruta Operativa

**Proyecto:** Opciones Americanas NU US Equity (Superficie de Volatilidad, Stress Testing y Trading)  
**Fecha de corte:** 21 de noviembre de 2026  
**Rama activa:** `fix/quant-audit-2026-11`  
**Estado:** Todos los hitos técnicos, auditoría cuantitativa y reparaciones numéricas implementados, ejecutados y verificados con 100% de éxito (37/37 pruebas aprobadas).

---

## 1. Trabajos Completados y Verificados

1. **Auditoría Forense y Depuración de Datos:**
   * Archivo original `Opciones_Completo.xlsx` respaldado intacto en `data/raw/`.
   * 575 contratos analizados (303 calls, 272 puts, 16 vencimientos).
   * Confirmación de operaciones del 17 de noviembre de 2026 ($S_0 = 12.33$ USD).
   * Recálculo exacto de $\tau$ en Act/365F continuo con corte a las 16:00 EST.
   * Clasificación en Tiers: 201 contratos limpios (Tier 1 + 2) exportados a `outputs/tables/options_clean.csv`.
   * Auditoría de paridad Call-Put en 68 pares idénticos documentando dispersión de 4.26 pp explicada por asincronía de `lastPrice` y bid-ask bounce.
2. **Motores de Valoración y Estabilidad de Griegas Americanas:**
   * `src/pricing_bs.py`: Black-Scholes analítico y derivadas exactas. Coincidencia analítica para Calls sin dividendos ($q=0, r \ge 0$).
   * `src/pricing_crr.py`: Árbol binomial CRR vectorizado de 1000 pasos como validador independiente.
   * `src/pricing_american_fd.py` y `src/greeks.py`: Esquema Crank-Nicolson con suavizado de Rannacher y método de penalización cuadrática (Forsyth & Vetzal, 2002).
   * **Reparación de Estabilidad Numérica (P0-A):** Dominio espacial común e invariante $S_{\max} = 4.0 \cdot \max(S_0, K)$ para evaluar perturbaciones sobre la misma malla discreta mediante interpolación PCHIP local. Gamma de la Put $K=12$ estabilizado de $3.3547$ a **$0.2375$** (en concordancia con Gamma europeo de $0.2346$).
3. **Inversión Numérica a Volatilidad Implícita:**
   * `src/iv_inversion.py`: Algoritmo de Brent implementado con bracketing estricto $[0.01, 5.00]$.
   * Contraste con Bloomberg mediante merge `1:1` estricto en `outputs/tables/iv_comparison_bloomberg.csv`.
   * Distinción transparente entre convergencia por tolerancia de precio vs tolerancia de volatilidad.
4. **Superficie de Volatilidad Implícita SVI:**
   * `src/surface.py`: Parametrización Raw SVI y splines monótonos PCHIP en log-forward moneyness $k$.
   * **Cotas Asintóticas y Ausencia de Arbitraje (P0-C):** Imposición estricta de la cota de momentos de Roger Lee $b(1+|\rho|) \le 1.95 < 2.0$ y densidad mariposa $g(k) \ge 0$ al **100.0%** en la malla empírica.
   * Eliminación analítica de arbitraje de calendario mediante acumulación monótona previa e interpolación PCHIP temporal ($\partial w / \partial \tau \ge 0$).
   * Política de Fallback conservador a PCHIP para cortes con menos de 6 strikes o subidentificados.
   * **Validación Cruzada Leave-One-Strike-Out:** 197 contratos evaluados fuera de muestra con pricing americano en puts (MAE Precio = **$\$0.0389$ USD**, RMSE = **$\$0.0649$ USD**).
5. **Comparación Cuantitativa de Modelos:**
   * `src/model_comparison.py`: Matriz $2 \times 2$ (Europeo/Americano $\times$ Plano/Superficie). Distinción formal entre ajuste In-Sample ($N=201$) y validación Out-of-Sample LOO ($N=197$). El modelo M4 reduce el MAE en un 40.9% general y en un 48.4% en opciones ITM.
6. **Portafolio Hipotético y Griegas:**
   * `src/portfolio.py` y `src/greeks.py`: Cartera delta-neutral de 5 patas con cobertura dinámica de **-357 acciones de NU** ($\Delta_{\text{neto}} = +0.11$).
7. **Stress Testing de Cadena Fija Unificado (P0-B):**
   * `src/stress_testing.py`: Contabilidad dual limpia.
   * Escenario Nulo (S0) incorporado: $\text{P\&L} \equiv 0.00$ USD tanto en PDE como en Taylor.
   * Diferencia inicial Mark-to-Model aislada ($-\$20.43$ USD).
   * Suma de patas reconciliada al céntimo con el total de cartera.
   * Requerimiento de margen regulatorio (Reg T / FINRA 4210) adoptado como Capital Económico ($\$5\,435.31$ USD).
   * Discrepancia de Taylor en Crisis Severa corregida y desmitificada: de $-\$3\,253$ USD a **$-\$261.15$ USD** (Full EDP $= +\$496.56$ USD vs Taylor $= +\$757.71$ USD).
8. **Estrategias Cuantitativas de Trading:**
   * `src/forecasts.py`: Modelo HAR-RV (Corsi, 2009) estimado causalmente mediante validación **walk-forward purificada** ($s \le t - 21$), eliminando cualquier fuga de información contemporánea (QLIKE = **$0.1855$**, RMSE = **$15.04$ pp**).
   * Pronóstico a 21 días = 72.97% vs IV ATM = 44.02% (señal $z = +0.505 > 0$).
   * `src/strategies.py`: Estrategia 1 (Straddle delta-neutral con cobertura de -23 acciones de NU derivada del delta americano) y Estrategia 2 (Calendar spread en strike 13.00 con volatilidad forward fija = 38.15%).
9. **Suite de Pruebas Automatizadas:**
   * **37 pruebas unitarias y de regresión** en `tests/` con 100% de aprobación (`pytest -v`).
10. **Documentación Formal:**
    * `docs/MANUAL_MATEMATICO_COMPLETO.tex` compilado a `docs/MANUAL_MATEMATICO_COMPLETO.pdf` (24 páginas).
    * `docs/AUDITORIA_REPARACION_BASELINE.md` y `docs/INFORME_FINAL_REPARACION.md`.
    * `docs/GUIA_EXPOSICION_10_MIN.md` y `docs/PREGUNTAS_DEFENSA.md`.
    * `docs/DECISIONES_Y_LIMITACIONES.md` (DEC-001 a DEC-009).
    * `requirements.txt` fijado y reproducible.

---

## 2. Comandos Clave de Verificación

```bash
# 1. Ejecutar pipeline integral determinista (incluye pytest automático)
python run_all.py

# 2. Correr suite completa de 37 pruebas unitarias
pytest -v

# 3. Recompilar manual en PDF
pdflatex -interaction=nonstopmode -output-directory=docs docs/MANUAL_MATEMATICO_COMPLETO.tex
```
