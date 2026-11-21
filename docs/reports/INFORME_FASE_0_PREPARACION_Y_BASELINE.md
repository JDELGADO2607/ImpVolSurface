# INFORME DE IMPLEMENTACIÓN — FASE 0: PREPARACIÓN Y BASELINE HESTON

**Proyecto Académico:** Valoración y Superficie de Opciones Americanas NU (NYSE: NU)  
**Fecha de Referencia Histórica:** 17 de noviembre de 2026, 16:00:00 EST (America/New_York)  
**Rol de Agente:** Gemini CLI (Implementador)  
**Supervisor / Auditor:** Codex (Coordinador Independiente)  
**Estado:** `PHASE_READY_FOR_AUDIT`  
**Rama de Implementación:** `JDELGADO2607/heston-implementation`  
**Worktree:** `C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-implementation`  
**Base Publicada de Coordinación Verificada:** `cf6c99053946bb0f610a11463c46e43ccf6967ce`  
**Referencia SVI Congelada:** `3d81ff18cae3a9f8dc74c174015fed17031a8da8` (PR #1, rama `fix/quant-audit-2026-11`)  
**Fecha de Ejecución:** 21 de noviembre de 2026  

---

## 1. Resumen Ejecutivo de la Fase 0

La Fase 0 establece la base técnica, empírica y metodológica inmutable requerida para la migración controlada al modelo de Heston clásico, conforme a la decisión humana del 21-nov-2026 y las directrices de `docs/orchestration/PHASE_0_START.md`.

### Logros Principales:
1. **Inspección e Inmutabilidad de SVI:** Se inspeccionó el PR #1 (commit congelado `3d81ff18cae3a9f8dc74c174015fed17031a8da8`). Todo el código histórico (`src/surface.py`, `src/iv_inversion.py`, `src/pricing_american_fd.py`, etc.) y sus salidas oficiales en `outputs/tables/` y `outputs/figures/` se mantienen intactos sin ninguna eliminación.
2. **Entorno y Dependencia QuantLib:** Se constató la disponibilidad de QuantLib 1.44 bajo Python 3.12.6, instalado limpiamente vía rueda precompilada binaria estándar (`quantlib-1.44-cp39-abi3-win_amd64.whl`), sin incurrir en costes, dependencias propietarias ni cambios de permisos del sistema.
3. **Auditoría Forense de la Cadena y Selección de Puts:** De los 575 contratos brutos y 272 opciones Put en `data/raw/Opciones_Completo.xlsx`:
   - 141 puts fueron rechazadas por cotizaciones obsoletas (`lastTradeDate` anterior al 17-nov-2026).
   - 25 puts negociadas el 17-nov fueron rechazadas por violar la cota inferior americana estricta ($P_{obs} < \max(K - S_0, 0)$), atribuible a asincronía intradía (ejecutadas durante la sesión cuando $S_t \in [12.70, 12.83]$ USD frente al cierre oficial $S_0 = 12.33$ USD).
   - 9 puts corresponden a cotizaciones de tick mínimo o microestructura ($P_{obs} \le 0.01$ USD o valor temporal nulo).
   - 97 puts limpias cumplen todas las condiciones económicas y de liquidez.
   - 84 puts coinciden exactamente con la muestra común histórica de SVI R3, garantizando una comparación 1:1 rigurosa.
4. **Resolución Definitiva de Tasas del Tesoro (H-R3-4):**
   - Se concilió la procedencia oficial de la curva de rendimientos par del US Department of the Treasury para el 17-nov-2026 (14 vencimientos desde 1M hasta 30Y).
   - Se documentó el timestamp de disponibilidad: cotizaciones OTC de cierre capturadas a las 15:30 EST y publicadas en la web oficial entre las 17:00 y 18:00 EST. Se adopta una política de **alineación contemporánea ex-post de cierre** (estándar de cierre contable/riesgos).
   - Se implementó un algoritmo exacto de **bootstrap de bonos con cupón** que reprecia todos los bonos par nocionales a 100.000000 USD (error residual máximo $< 0.05$ USD en el tramo de opciones), distinguiéndolo matemáticamente de la mera conversión de frecuencia empleada en SVI R3.
   - Se realizó la ablación formal entre curvas: el impacto en las tasas del tramo de opciones es de apenas 0.87 a 1.96 pb, afectando los precios teóricos en menos de $0.0003$ USD.
5. **Malla de Benchmarks y Límites de SVI:**
   - Evaluado sobre la muestra común de 84 puts:
     - $BS_{Euro}$ Plano ($\sigma=0.45$): $\text{MAE} = 0.0428$ USD, $\text{RMSE} = 0.0670$ USD.
     - $Amer_{const}$ Plano ($\sigma=0.45$ vía QuantLib 1.44): $\text{MAE} = 0.0391$ USD, $\text{RMSE} = 0.0596$ USD.
     - $SVI_{frozen}$ Americano (R3): $\text{MAE} = 0.0684$ USD, $\text{RMSE} = 0.0886$ USD.
   - Se constata que el modelo SVI calibrado en varianza total presenta un sesgo positivo sistemático en dólares ($+0.067$ USD) en puts fuera del dinero.
6. **Partición Determinista Libre de Fuga:**
   - Se generó una partición estructural determinista: Train (61.9%, 60 puts), Holdout de Strike intercalado (22.7%, 22 puts), Holdout de Tenores completos (15.5%, 15 puts en vencimientos 37d, 94d y 304d) y Contraste Externo de Calls (142 calls limpias).
7. **Presupuesto Numérico y Puerta Cuantitativa para PoC (Fase 1):** Propuesta cuantitativa formulada y congelada **antes** de cualquier calibración de Heston.
8. **Recuperación de Requisitos Académicos 46–56:** Mapeo secundario recuperado íntegramente desde `docs/00_Alcance_y_auditoria.md`. Se declara formalmente la limitación de ausencia del enunciado original en el repositorio.
9. **Aislamiento Total de Salidas y Cero Escrituras Oficiales:** Todos los entregables residen exclusivamente en `data/heston/`. La suite completa de 7 pruebas unitarias e integración en `tests/test_heston_phase0.py` pasó al 100% en 6.49s, verificando la ausencia de modificaciones en archivos históricos (Finding M-R3-2).

---

## 2. Inspección del PR #1 y Congelación de SVI (Alcance 1)

### 2.1 Estado del Repositorio y Módulos
- **PR #1:** `fix/quant-audit-2026-11`, commit de cierre `3d81ff18cae3a9f8dc74c174015fed17031a8da8`.
- **Módulos SVI Congelados:**
  - `src/surface.py`: Parametrización Raw SVI por rebanadas, regularización de alas Roger Lee y splines en $w(k, \tau)$. Se conservan sus funciones para reproducir el benchmark histórico.
  - `src/iv_inversion.py`: Algoritmo de Brent para inversión de volatilidad implícita Black-Scholes.
  - `src/pricing_american_fd.py`: Resolvedor Crank-Nicolson 1D con Rannacher time-stepping para opciones americanas bajo volatilidad local/constante.
  - `src/pricing_bs.py`: Fórmulas analíticas cerradas europeas.
  - `src/pricing_crr.py`: Árbol binomial de Cox-Ross-Rubinstein.
- **Módulos Reutilizables para Heston:**
  - `src/pricing_american_fd.py`: Sirve como control 1D independiente para el ejercicio americano bajo volatilidad plana.
  - `src/pricing_bs.py`: Cálculo analítico de precios europeos para control y validación de paridad.
  - `src/data_cleaning.py`: Lógica de parseo OCC y normalización Bloomberg.

### 2.2 Entorno de Dependencias y QuantLib
- **Python:** 3.12.6 (Windows AMD64).
- **NumPy:** 2.1.1 | **SciPy:** 1.18.0 | **Pandas:** 2.2.2 | **Pytest:** 9.2.0.
- **QuantLib:** Versión **1.44** instalada mediante `pip install QuantLib` utilizando la rueda oficial preconstruida `quantlib-1.44-cp39-abi3-win_amd64.whl`.
  - Coste: $0.00 USD.
  - Permisos: Instalación de usuario estándar, sin privilegios administrativos.
  - Reproducibilidad: Totalmente determinista y empaquetada. Verificada mediante `import QuantLib as ql; ql.__version__ == '1.44'`.

---

## 3. Auditoría Forense de Datos y Selección Efectiva de Puts (Alcance 2)

### 3.1 Parámetros de Mercado Auditados
- **Spot de Referencia ($S_0$):** $12.33$ USD. Verificado contra el cierre oficial de NYSE del 17 de noviembre de 2026 y conciliado con `data/processed/nu_historical_daily.csv` (cierre $12.3299999237$).
- **Rendimiento por Dividendos ($q$):** $0.00\%$ anual. Hipótesis confirmada por la ausencia de dividendos históricos de Nu Holdings Ltd. (SEC Form 6-K).
- **Convención de Tiempo:** ACT/365F continuo. La madurez exacta $\tau$ se calcula entre la marca temporal de valoración (`2026-11-17 16:00:00 America/New_York`) y las `16:00:00 America/New_York` de cada fecha de vencimiento contractual, teniendo en cuenta las variaciones de horario de verano (EST/EDT).
- **Multiplicador de Contrato:** 100 acciones.
- **Integridad de Fuentes:**
  - `data/raw/Opciones_Completo.xlsx`: SHA-256 `306f8d3c1a52c7a67952d08881516bdc8632856e3abd6b33de373c4bc77ffb53` (Inmutable).
  - `data/processed/nu_historical_daily.csv`: SHA-256 `a510f9a48eaa0fc4f95cfbfcda491de09f4a6b14956efb0f3959c7c57ac5989a` (Inmutable).

### 3.2 Taxonomía de Clasificación de las 272 Opciones Put
La auditoría de las 272 opciones put originales arrojó la siguiente descomposición exhaustiva:

| Categoría | Cantidad | Porcentaje | Motivo / Criterio Forense |
|---|---:|---:|---|
| **REJECTED_STALE_TRADE** | 141 | 51.8% | Última transacción anterior al 17-nov-2026 (antigüedad de 1 a 420+ días). Cotización obsoleta no representativa del cierre. |
| **REJECTED_BOUNDS_VIOLATION** | 25 | 9.2% | Violación de la cota inferior americana estricta ($P_{obs} < \max(K - S_0, 0)$). Causada por asincronía de ejecución intradía. |
| **CANDIDATE_MICROSTRUCTURE_SENSITIVE** | 9 | 3.3% | Cotizaciones en el tick mínimo del exchange ($P_{obs} \le 0.01$ USD) o valor temporal nulo ($< 0.01$ USD) en alas profundas. |
| **SELECTED_CLEAN** | 97 | 35.7% | Transadas el 17-nov, cotas americanas satisfechas, $P_{obs} \ge 0.02$ USD y valor temporal $\ge 0.01$ USD. |
| **Total Puts en Bruto** | **272** | **100.0%** | Cadena completa en Hoja1 de `Opciones_Completo.xlsx`. |

### 3.3 El Fenómeno de Asincronía Intradía (25 Puts Violatorias)
Las 25 opciones put que violan la cota inferior $P_{obs} \ge K - S_0$ se concentran principalmente en el vencimiento ultra corto del 20-nov-2026 ($\tau = 3.0$ días, 19 contratos violatorios con strikes entre 13.5 y 30.0 USD).
- **Causa Forense:** Estas operaciones se ejecutaron durante la mañana del 17-nov-2026 (entre las 10:00 y las 14:00 NY), momento en el cual la acción de NU cotizaba en su máximo intradía de **12.83 USD**. Al liquidar una put $K=14.0$ con $S_t \approx 12.80$, un precio de $1.64$ USD era económicamente válido. Sin embargo, al comparar ese precio contra el cierre de $S_0 = 12.33$ USD, el valor intrínseco de cierre es $14.00 - 12.33 = 1.67$ USD, arrojando una aparente violación de 3 centavos ($P_{obs} - \text{intr} = -0.03$ USD).
- **Decisión Metodológica:** Ningún modelo de valoración americana libre de arbitraje (ni Heston, ni árbol binomial, ni diferencias finitas) puede generar un precio inferior al valor intrínseco de ejercicio inmediato. Incluir estas 25 opciones distorsionaría gravemente la frontera de ejercicio anticipado de la calibración de Heston. Por tanto, quedan formalmente **excluidas** y registradas con su magnitud exacta de desvío en `data/heston/puts_selection_all.csv`.

### 3.4 Soporte por Vencimiento
La muestra limpia de puts se distribuye a lo largo de los 16 vencimientos contractuales:
- **Rebanadas Robustas ($\ge 5$ puts limpias):** 11 vencimientos (3d, 10d, 17d, 24d, 31d, 37d, 44d, 59d, 94d, 122d, 212d, 430d, 794d).
- **Rebanadas Adecuadas (3–4 puts limpias):** 2 vencimientos (304d con 3 puts, 395d con 3 puts).
- **Rebanadas Dispersas (1–2 puts limpias):** 1 vencimiento (150d con 2 puts: $K=11$ y $K=12$).
- No se fuerza un tamaño arbitrario ni un mínimo de 200 filas. Se conserva la estructura natural del mercado.

---

## 4. Resolución de Procedencia de Tasas Deterministas (Alcance 3, Finding H-R3-4)

### 4.1 Conciliación de la Curva Oficial del Tesoro
Se resolvió la discrepancia identificada por Codex en el hallazgo H-R3-4 (donde la versión R3 conservaba tasas del 18-nov con desvíos de 1 a 3 pb).

La curva oficial **Daily Treasury Par Yield Curve Rates** para el **17 de noviembre de 2026**, obtenida de la fuente gubernamental oficial (`home.treasury.gov`), consta de las siguientes tasas par anuales (CMT):

| Tenor | Plazo ($t$) | CMT Par Oficial 17-Nov | Par R3 Histórico | Desvío Oficial vs R3 |
|---|---:|---:|---:|---:|
| **1M** | 0.0833 y | **4.09 %** | 4.10 % | -1.0 pb |
| **1.5M** | 0.1250 y | **4.24 %** | 4.24 % | 0.0 pb |
| **2M** | 0.1667 y | **4.26 %** | 4.27 % | -1.0 pb |
| **3M** | 0.2500 y | **4.33 %** | 4.34 % | -1.0 pb |
| **4M** | 0.3333 y | **4.32 %** | 4.35 % | -3.0 pb |
| **6M** | 0.5000 y | **4.41 %** | 4.43 % | -2.0 pb |
| **1Y** | 1.0000 y | **4.60 %** | 4.62 % | -2.0 pb |
| **2Y** | 2.0000 y | **4.80 %** | 4.80 % | 0.0 pb |
| **3Y** | 3.0000 y | **4.84 %** | 4.84 % | 0.0 pb |
| **5Y** | 5.0000 y | **4.90 %** | 4.90 % | 0.0 pb |
| **7Y** | 7.0000 y | **4.99 %** | N/A | Base añadida |
| **10Y** | 10.0000 y | **5.10 %** | 5.10 % | 0.0 pb |
| **20Y** | 20.0000 y | **5.50 %** | N/A | Base añadida |
| **30Y** | 30.0000 y | **5.46 %** | N/A | Base añadida |

### 4.2 Timestamp de Disponibilidad y Política Temporal
- **Mecanismo de Publicación:** El Departamento del Tesoro calcula los rendimientos CMT utilizando cotizaciones indicativas de compra (closing bid yields) del mercado secundario OTC recibidas por el Federal Reserve Bank of New York alrededor de las 15:30 EST. Las tasas se procesan y publican en `home.treasury.gov` habitualmente entre las 17:00 y las 18:00 EST.
- **Justificación de la Política Adoptada:** Se adopta formalmente una política de **alineación contemporánea de cierre ex-post** (contemporaneous closing ex-post alignment). En la práctica cuantitativa institucional de valoración de carteras al cierre (EOD), la curva de tasas de cierre del día $T$ se aparea con las cotizaciones de cierre de acciones y opciones del mismo día $T$.
- **Contraste Ex-Ante:** De haberse exigido una tasa estrictamente previa a las 16:00 EST (ex-ante), habría correspondido usar el cierre del 16-nov-2026 (donde 1M era 4.10% y 1Y era 4.62%). La diferencia entre ambas fechas es de apenas 1 a 2 pb, careciendo de materialidad económica para la valoración de opciones a corto y medio plazo.

### 4.3 Bootstrap Cuantitativo vs Conversión de Frecuencia
Se implementó en `src/heston/rates_curve.py` un motor riguroso de **bootstrap de bonos con cupón**, diferenciándolo explícitamente de la conversión de frecuencia:
1. **Tramo Corto ($t \le 0.5$ años, Letras del Tesoro):**
   $$D(0, t) = \frac{1}{1 + y \cdot t}, \quad r_{zero}(t) = -\frac{\ln D(0, t)}{t}$$
2. **Tramo con Cupón ($t > 0.5$ años, Bonos Semestrales con $c = y/2$):**
   $$100 = \sum_{i=1}^{2T-1} 100 \cdot \frac{y}{2} D(0, t_i) + 100 \cdot \left(1 + \frac{y}{2}\right) D(0, T)$$
   $$D(0, T) = \frac{1 - \frac{y}{2} \sum_{i=1}^{2T-1} D(0, t_i)}{1 + \frac{y}{2}}$$
   Donde los factores de descuento en fechas intermedias de cupón $t_i$ se interpolan log-linealmente (tasa forward constante).
3. **Comprobación de Repreciación:**
   Todos los bonos par nocionales del tramo relevante de opciones ($\le 2.17$ años) reprecian a exactamente **100.000000 USD** con error $< 0.003$ USD.

### 4.4 Estudio de Ablación de Tasas
La comparación directa entre la curva Bootstrap Oficial 11/17, la conversión Par 11/17 y la curva Histórica R3 sobre vencimientos representativos arrojó:

| Tenor ($\tau$) | $r_{boot}$ | $r_{par}$ | $r_{R3}$ | Dif. Boot vs Par | Dif. Boot vs R3 | $D_{boot}$ | Dif. Forward |
|---|---:|---:|---:|---:|---:|---:|---:|
| **3.0 d** | 4.0830 % | 4.0830 % | 4.0930 % | 0.00 pb | -1.00 pb | 0.999664 | 0.00 c |
| **10.0 d** | 4.0830 % | 4.0830 % | 4.0930 % | 0.00 pb | -1.00 pb | 0.998882 | 0.00 c |
| **31.0 d** | 4.0886 % | 4.0886 % | 4.0982 % | 0.00 pb | -0.96 pb | 0.996533 | -0.01 c |
| **59.0 d** | 4.2430 % | 4.2430 % | 4.2517 % | 0.00 pb | -0.87 pb | 0.993165 | -0.02 c |
| **94.0 d** | 4.3051 % | 4.3051 % | 4.3168 % | 0.00 pb | -1.17 pb | 0.988974 | -0.04 c |
| **1.0 y** | 4.5500 % | 4.5479 % | 4.5674 % | +0.21 pb | -1.74 pb | 0.955519 | -0.22 c |
| **2.0 y** | 4.7504 % | 4.7433 % | 4.7433 % | +0.71 pb | +0.71 pb | 0.909365 | +0.19 c |

**Conclusión de Materialidad:** En todo el horizonte de opciones NU ($\tau \le 2.17$ años), el desvío máximo de tasa no supera los 1.96 pb y la diferencia máxima inducida en el precio forward es de apenas 0.22 centavos. El impacto en el pricing de opciones es inferior a 0.03 centavos de dólar.

---

## 5. Malla de Benchmarks sobre Muestra Común y Límites de SVI (Alcance 4)

Se evaluaron los modelos de referencia sobre la **muestra común de 84 puts** (coincidente entre el benchmark SVI R3 y la nueva selección):

### 5.1 Métricas de Error en Precios (USD)

| Modelo | $N$ | MAE (USD) | RMSE (USD) | Error Máx (USD) | Sesgo Medio (USD) |
|---|---:|---:|---:|---:|---:|
| **M1: Black-Scholes Europeo Plano ($\sigma=0.45$, Tasas Oficiales)** | 84 | 0.0428 | 0.0670 | 0.3214 | -0.0126 |
| **M2: Americano Plano ($\sigma=0.45$, QuantLib 1.44, Tasas Oficiales)** | 84 | **0.0391** | **0.0596** | 0.3313 | +0.0138 |
| **M3: SVI Americano Congelado (R3, Curva Histórica)** | 84 | 0.0684 | 0.0886 | 0.2463 | +0.0674 |
| **M3: SVI Americano Congelado (Tasas Oficiales 11/17)** | 84 | 0.0687 | 0.0889 | 0.2469 | +0.0678 |

### 5.2 Diagnóstico Cuantitativo y Limitaciones de SVI (Sin Repararlo)
1. **Sesgo en Dólares de SVI:** A pesar de haber sido ajustado con splines y regularización en varianza total, SVI R3 arroja un MAE de $0.0684$ USD en puts, superior al modelo americano con volatilidad plana del 45% ($0.0391$ USD). La razón radica en que la calibración de SVI minimizó el residuo cuadrático en el espacio de volatilidades implícitas ($\sigma_{SVI} - \sigma_{mkt}$), donde un pequeño desajuste en alas OTM induce un error sustancial y un sesgo alcista de $+0.067$ USD en precios monetarios.
2. **Prima de Ejercicio Anticipado:** La prima media de ejercicio anticipado ($P_{Amer} - P_{Euro}$) observada en la muestra común es de **0.0270 USD** (2.7 centavos), alcanzando un máximo de **0.5007 USD** en puts profundas dentro del dinero a vencimientos largos.
3. **Ablación de Curva en SVI:** El MAE de SVI apenas varió de $0.0684$ USD a $0.0687$ USD al sustituir las tasas de R3 por las tasas oficiales de 11/17. Esto prueba que la limitación de SVI es estrictamente estructural del modelo y de su espacio de calibración, no de las tasas.

---

## 6. Partición Determinista y Propuesta Cuantitativa de Puerta PoC (Alcance 5)

### 6.1 Partición Determinista Libre de Fuga
Para la calibración de Heston en Fase 1, se diseñó una partición estructural que evita la fuga de información espacial y temporal:
- **Tenor Holdout (15.5%, 15 puts):** Vencimientos completos retenidos para evaluar la extrapolación de la estructura temporal:
  - Corto/Intermedio: `2026-12-24` ($\tau = 37.0$ d, 7 puts)
  - Intermedio: `2027-02-19` ($\tau = 94.0$ d, 5 puts)
  - Largo: `2027-09-17` ($\tau = 304.0$ d, 3 puts)
- **Strike Holdout (22.7%, 22 puts):** Retención intercalada (cada 3er strike, protegiendo extremos y ATM) sobre los 13 vencimientos de entrenamiento.
- **Train Set (61.9%, 60 puts):** Conjunto núcleo utilizado exclusivamente para calibrar el vector de parámetros globales de Heston $\Theta = (\kappa, \theta, \sigma_v, \rho, v_0)$.
- **Contraste Externo de Calls (142 calls):** Calls con cotas satisfechas transadas el 17-nov, reservadas exclusivamente como control fuera de muestra.

### 6.2 Presupuesto Numérico y Puerta Cuantitativa para Fase 1 (PoC)
Conforme a `ACCEPTANCE_CRITERIA.md`, se formula la siguiente propuesta cuantitativa **antes** de observar los resultados de calibración de Heston:

1. **Presupuesto de Error Numérico del Solver:**
   - La tolerancia del solver de diferencias finitas (QuantLib `FdHestonVanillaEngine`) debe ser $\le 0.002$ USD (0.2 centavos), garantizando que el error numérico sea un orden de magnitud inferior al tick mínimo de mercado ($0.01$ USD).
2. **Criterios de Aceptación In-Sample (Train):**
   - No se exige batir in-sample a SVI (que poseía $5 \times 16 = 80$ parámetros libres locales frente a solo 5 parámetros estructurales globales de Heston).
   - $\text{MAE}_{in} \le \mathbf{0.080}$ USD ($8.0$ centavos, $< 0.65\%$ del spot).
   - $\text{RMSE}_{in} \le \mathbf{0.120}$ USD ($12.0$ centavos).
   - Error relativo máximo en opciones at-the-money ($|k| \le 0.10$): $\le 10\%$.
3. **Criterios de Generalización (Holdout):**
   - El desvío de generalización $(\text{MAE}_{holdout} - \text{MAE}_{train}) / \text{MAE}_{train}$ no debe superar el **30%**, descartando sobreajuste numérico.
   - $\text{MAE}_{holdout} \le \mathbf{0.100}$ USD ($10.0$ centavos).
4. **Plausibilidad Económica e Identificación:**
   - $\kappa \in [0.1, 15.0]$, $\theta \in [0.01, 1.5]$, $v_0 \in [0.01, 1.5]$, $\sigma_v \in [0.05, 3.0]$, $\rho \in [-0.95, 0.0]$.
   - Condición de Feller: calcular y reportar el ratio $2\kappa\theta / \sigma_v^2$. Si el ratio es $< 1$, documentar el comportamiento de frontera en $v=0$ sin forzar filtros artificiales.
   - Multistart: Ejecución obligatoria de al menos 5 puntos de inicio dispersos. Las soluciones con objetivo dentro del 5% del óptimo deben presentar cercanía paramétrica, o documentar explícitamente la indeterminación paramétrica.
5. **Coste Computacional:** Tiempo medio de calibración por arranque inferior a 60 segundos.

---

## 7. Requisitos Académicos 46–56 y Declaración de Límites (Alcance 6)

Se recuperó el mapeo secundario disponible en `docs/00_Alcance_y_auditoria.md`:

| Punto | Requisito Académico Reportado | Cobertura en Fase 0 |
|---|---|---|
| **46** | Cadena de calls y puts por strike y vencimiento | 575 contratos auditados íntegramente en `puts_selection_all.csv`. |
| **47** | Spot, tasas y dividendos | $S_0=12.33$, $q=0$, curva Treasury 17-nov conciliada y con bootstrap. |
| **48** | Black-Scholes europeo | Modelo M1 implementado y evaluado en `baseline_comparison_detailed.csv`. |
| **49** | Inversión numérica de IV | Conservado en `src/iv_inversion.py` para análisis de contraste. |
| **50** | Sonrisas, moneyness y skew | Moneyness $k = \ln(K/F)$ computado para cada contrato en la selección. |
| **51** | Superficie de volatilidad | SVI congelado evaluado en M3; base lista para Heston 2D en Fase 1+. |
| **52** | Stress testing de cadena fija | Módulos históricos preservados; escenarios preparados para Fase 6. |
| **53** | Cartera y estrategias de volatilidad | Cartera histórica conservada; integración fijada para Fase 6. |
| **54** | Comparación europeo/americano y vol constante | Matriz comparativa generada en `baseline_comparison_summary.csv`. |
| **55** | Griegas y riesgo de skew | Módulos 1D conservados; cálculo Heston programado para Fase 6. |
| **56** | Recomendaciones ejecutivas y defensa 10 min | Restricciones de diseño incorporadas en la propuesta de tolerancias. |

> [!WARNING]
> **Declaración de Limitación:** El enunciado original literal del examen emitido por el profesor no se encuentra presente en el repositorio. Se adopta con rigor el mapeo secundario estructurado previamente, sin inventar citas textuales ni alterar los requisitos académicos fijados.

---

## 8. Verificación Técnica, Hashes e Inmutabilidad (Alcance 7)

### 8.1 Resultados de las Pruebas Unitarias
Se ejecutó la suite completa de pruebas en `tests/test_heston_phase0.py`:
```powershell
pytest tests/test_heston_phase0.py -v
```
**Resultado:** `7 passed in 6.49s`
- `test_source_data_immutability`: PASSED (Verifica hashes inmutables de Excel y CSV diario).
- `test_treasury_rates_and_bootstrap`: PASSED (Verifica monotonicidad de $D$, $F = S_0/D$ y repreciación par).
- `test_occ_parsing`: PASSED (Verifica exactitud de descomposición OCC).
- `test_option_audit_and_selection`: PASSED (Verifica conteos exactos: 272 puts, 141 obsoletas, 25 violatorias, 84 comunes).
- `test_deterministic_data_split`: PASSED (Verifica ausencia de solapamiento, exclusión de calls y reproducibilidad).
- `test_baseline_pricing_engine`: PASSED (Verifica $P_{Amer} \ge P_{Euro}$, $P_{Amer} \ge \text{intrínseco}$, precios finitos).
- `test_no_writes_to_official_directories`: PASSED (Garantiza cero escrituras en `outputs/tables/` y `outputs/figures/`).

Adicionalmente, se ejecutó la suite completa preexistente (`pytest -q`), obteniendo **62 passed** sin regresiones.

### 8.2 Manifiesto de Entregables Generados en `data/heston/`

| Archivo Generado | Tamaño | SHA-256 |
|---|---:|---|
| `phase0_execution_manifest.json` | 6.27 KB | `cf61b1836166bc6225586ae79dcf714909a826477d9c6cf0488950d877cf91c4` |
| `rates_treasury_manifest.json` | 1.91 KB | `c11049d859c9699bff69cfc98134daf306ad7210f0898c15976594b4b93d8fb1` |
| `rates_curve_comparison.csv` | 915 B | `54bb533fdf503cf14aca81f958c8f111d103c0eaef0428894986cc552683f3ea` |
| `rates_par_bonds_repricing.csv` | 1.21 KB | `751a33518d2af79a8c9953b0a4543464e99ef226f7e5228fcb4dc94dc576c5f0` |
| `puts_selection_all.csv` | 95.76 KB | `76e1f9ae8b67bf0d469b5e23267f13fe7d41059900ffd9f5a8ab8b099f36a5a4` |
| `puts_selected_clean.csv` | 32.73 KB | `6e5e84117def9da6ed2b90e80e0e9070e43138a70a2355551bcdab0e38bb897f` |
| `puts_common_r3_benchmark.csv` | 28.51 KB | `b36617c54f620908ea667a942be9aac4edf9420d9ef3ce98b55c48638fa0f0c8` |
| `puts_support_by_tenor.csv` | 1.49 KB | `6c4d6263ca036956dcb5ead781c6ad0860e026a845deb161cdbb427e9f727d28` |
| `calls_external_contrast_all.csv` | 105.46 KB | `7f9faf6ec12a66543bd1ccf03c0f4eea653b9dc84240720e0c677b9bfd450068` |
| `data_split_manifest.json` | 2.91 KB | `981345af41c4b68ef0c0733aab80bbbdc46a9b6c924a7206193fb11a5e06ce0f` |
| `data_split_train.csv` | 20.47 KB | `f3794c401b80329dd24210a137351aefbc53620b2ca933a8e95cd42232b97720` |
| `data_split_strike_holdout.csv` | 7.67 KB | `cac223d46ff3a9169ffa2b19e4fc7f89823c9773fb0f4a4219fe52075c08f731` |
| `data_split_tenor_holdout.csv` | 5.35 KB | `14eac394b0d607407940246a36ac0edd1fc6f65599879d83a1704734097e4ae0` |
| `data_split_calls_contrast.csv` | 48.11 KB | `091c182af26f411683789d692ace41bdf1cc2f7fe528f9b188c24dffdb8c2713` |
| `baseline_comparison_detailed.csv` | 28.62 KB | `1c31f68b7d4ad674ca8f909e58d69a14d9ff21dbaabaee899ecf2e6ebc71a870` |
| `baseline_comparison_summary.csv` | 490 B | `276e05602725917a090361537fac2bee8875a99688ea93c73ac3610e63aac320` |

---

## 9. Próximos Experimentos (Fase 1: Gate PoC QuantLib)

Tras la aprobación técnica de Codex para la Fase 0, la Fase 1 abordará:
1. Instanciación del proceso de Heston en QuantLib (`ql.HestonProcess`) con parametrización inicial informada por la varianza realizada ($v_0 \approx 0.20$).
2. Configuración de `ql.FdHestonVanillaEngine` acoplado con `ql.AmericanExercise` sobre la muestra de entrenamiento de puts.
3. Ejecución de calibración multi-inicio (5 starts) minimizando la suma de errores cuadráticos no ponderados en dólares:
   $$\min_{\Theta} \sum_{i \in \text{Train}} (P_{Heston}^{Amer}(S_0, K_i, T_i; \Theta) - P_{market, i})^2$$
4. Evaluación del Gate PoC frente a los umbrales preestablecidos ($\text{MAE} \le 0.08$ USD, brecha de holdout $\le 30\%$).
