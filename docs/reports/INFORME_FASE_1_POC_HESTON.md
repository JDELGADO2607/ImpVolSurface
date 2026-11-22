# Informe Técnico de Implementación — Fase 1: PoC Heston QuantLib (Remediación 3)

**Proyecto:** Migración Metodológica a Heston Clásico — Opciones Americanas NU  
**Rama:** `JDELGADO2607/heston-implementation`  
**Fecha de Valoración de Referencia:** 17-nov-2026 16:00:00 EST (Cierre NYSE)  
**Entorno de Ejecución:** Python 3.12.6, QuantLib 1.44, SciPy 1.18.0, NumPy 2.1.1, Pandas 2.2.2  
**Timestamp de Transcripción Histórica CMT:** `2026-11-21T16:20:00-05:00` (16:20 NY)  
**Timestamp de Ejecución de Pipeline:** `2026-11-21T23:41:08.481201+00:00` (Ejecución oficial vigente)  
**Dictamen Previo Vinculante:** `PHASE_REJECTED`, Remediation 3/3 autorizada (`docs/audits/HESTON_PHASE_1_3a294af.md`)  
**Veredicto de Gate Fase 1 (Remediación 3):** **`PASSED`** (Replay incondicional de todos los candidatos F1-04, selectores robustos, presupuesto numérico de malla F1-01, diagnósticos crudos F1-03 y reconciliación documental integral F1-02)

---

## 1. Resumen Ejecutivo y Cumplimiento de Gate

La Remediación 3 de la Fase 1 resuelve exhaustivamente los hallazgos residuales de auditoría **F1-04** (replay incondicional obligatorio para todos los candidatos sin exención por estado o pérdida, exclusión de no convergentes en selección y suite expandida de tests negativos) y **F1-02** (especificación rigurosa de las mallas dinámicas de calibración y validación fina, tolerancia determinista de replay en USD$^2$ y precisión en la cuadratura semi-analítica de QuantLib), manteniendo la plena conformidad con **F1-01** (malla productiva unificada) y **F1-03** (diagnósticos de cotas y no arbitraje sobre precios crudos).

### Cuadro de Cumplimiento de Criterios de Aceptación (Gate PoC)

| Métrica / Verificación | Criterio de Gate Predeclarado | Valor Obtenido | Estado |
| :--- | :--- | :--- | :---: |
| **Train MAE (60 puts)** | $\le 0.080$ USD | **0.0258 USD** (~2.6¢) | **PASS** |
| **Train RMSE (60 puts)** | $\le 0.120$ USD | **0.0380 USD** (~3.8¢) | **PASS** |
| **Strike Holdout MAE (22 puts)** | $\le 0.100$ USD | **0.0211 USD** (~2.1¢) | **PASS** |
| **Tenor Holdout MAE (15 puts)** | $\le 0.100$ USD | **0.0204 USD** (~2.0¢) | **PASS** |
| **Presupuesto Numérico de Malla** | $\le 0.0020$ USD | **Max \|Prod - Ultra\| = 0.000605 USD** | **PASS** |
| **Violaciones Cota Inferior (Cruda)** | 0 violaciones ($P_{\text{raw}} \ge \max(0, K-S_0)$) | **0 violaciones** (mínimo gap = $0.000000$) | **PASS** |
| **Violaciones Cota Superior** | 0 violaciones ($P_{\text{raw}} \le K$) | **0 violaciones** | **PASS** |
| **Violaciones Prima Ejercicio Temprano** | 0 violaciones ($P_{\text{raw}}^{Am} \ge P_{\text{raw}}^{Eu}$) | **0 violaciones** (mínimo gap = $0.000000$) | **PASS** |
| **Violaciones Monotonía en Strike** | 0 violaciones ($\partial P_{\text{raw}}/\partial K \ge -10^{-4}$) | **0 violaciones** | **PASS** |
| **Violaciones Monotonía Temporal ($K$ fijo)** | 0 violaciones ($P(T_2) \ge P(T_1) - 0.0020$) | **0 violaciones** (75 transiciones verificadas) | **PASS** |
| **Violaciones Convexidad en Strike** | 0 violaciones (Segundas diferencias divididas) | **0 violaciones** (Fronteras `NOT_TESTABLE`) | **PASS** |
| **Validación Criptográfica Caché (F1-04)** | Comparación hashes inputs, bounds, SSE $\ge 0$, replay | **100% verificada con tests negativos** | **PASS** |
| **Full Sample MAE (97 puts)** | Diagnóstico descriptivo | **0.0239 USD** (~2.4¢) | **INFO** |
| **Contraste Externo (142 calls)** | Diagnóstico out-of-sample | **0.0873 USD** (~8.7¢) | **INFO** |
| **Muestra Común (84 puts) vs SVI** | Comparativa frente a R3 ($0.0684$) | **0.0232 USD** vs $0.0684$ USD | **INFO** |
| **Muestra Común (84 puts) vs Flat** | Comparativa curva común ($0.0397$) | **0.0232 USD** vs $0.0397$ USD | **INFO** |
| **Condición de Feller ($2\kappa\theta/\xi^2$)** | Reporte sin filtros artificiales | **5.0180** ($> 1$, estrictamente satisfecha) | **INFO** |

---

## 2. Resolución F1-01: Malla Productiva Unificada y Refinamientos Separados

### 2.1 Causa Raíz de la Desviación Previa en NU270617P17 ($K=17, 212$d)
En la auditoría independiente de Codex (`HESTON_PHASE_1_d6a369c.md`), se descubrió que el contrato `NU270617P17` ($K=17, T=212$ días) exhibía un precio publicado de $4.760934$ USD bajo la malla antigua ($tFactor=100, x=100, v=50$), el cual al ser comparado con una malla de alta resolución ($tFactor=400, x=320, v=160 \implies 4.763189$ USD) difería en $0.002256$ USD, superando ligeramente el presupuesto de $0.0020$ USD. El análisis determinó que:
1. Existía un desacople entre la función de pricing de producción ($100 \times 50$) y la función de prueba de malla ($120 \times 60$).
2. La componente temporal dominaba: en plazos intermedios y largos, un factor temporal $tFactor=100$ resultaba insuficiente para capturar la curvatura de ejercicio anticipado en contratos ITM profundos.

### 2.2 Especificación de la Malla Productiva Unificada
Se unificó la resolución espacial y temporal de producción en `src/heston/heston_model.py`:
$$\begin{aligned}
t_{\text{steps}} &= \max(60, \text{round}(300.0 \times T)) \\
x_{\text{steps}} &= 160 \\
v_{\text{steps}} &= 80
\end{aligned}$$
Esta malla garantiza un paso temporal $\Delta t \le 0.0033$ años (~$1.2$ días) en cualquier horizonte, con una resolución en spot de $160$ nodos y en varianza de $80$ nodos.

### 2.3 Refinamientos Separados y Prueba Numérica
Se implementaron refinamientos separados en tiempo y espacio frente a la malla productiva:
1. **Refinamiento Temporal:** $tFactor = 500$ (mínimo $100$ pasos), $x = 160, v = 80$.
2. **Refinamiento Espacial:** $tFactor = 300$ (mínimo $60$ pasos), $x = 240, v = 120$.
3. **Refinamiento Ultra-Fino Conjunto:** $tFactor = 500$ (mínimo $100$ pasos), $x = 240, v = 120$.

#### Resultados en los 10 Contratos Representativos (incluyendo NU270617P17):

| Contrato | DTE | Strike | Precio Producción | Precio Ref. Temporal | Precio Ref. Espacial | Precio Ultra-Fino | \|Temp - Prod\| | \|Spat - Prod\| | \|Ultra - Prod\| | Presupuesto $\le 0.0020$ USD |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Short OTM** | 10 | 10.0 | 0.001120 | 0.001120 | 0.001116 | 0.001116 | 0.000000 | 0.000004 | **0.000004 USD** | **PASSED** |
| **Short ATM** | 10 | 12.0 | 0.206998 | 0.207005 | 0.207007 | 0.207016 | 0.000007 | 0.000010 | **0.000018 USD** | **PASSED** |
| **Short ITM** | 10 | 14.0 | 1.672362 | 1.672391 | 1.672363 | 1.672393 | 0.000029 | 0.000002 | **0.000032 USD** | **PASSED** |
| **Medium OTM** | 94 | 9.0 | 0.118161 | 0.118177 | 0.118166 | 0.118183 | 0.000016 | 0.000005 | **0.000022 USD** | **PASSED** |
| **Medium ATM** | 94 | 12.0 | 0.866968 | 0.867055 | 0.867016 | 0.867107 | 0.000087 | 0.000048 | **0.000138 USD** | **PASSED** |
| **Medium ITM** | 94 | 15.0 | 2.808217 | 2.808473 | 2.808195 | 2.808462 | 0.000256 | 0.000022 | **0.000245 USD** | **PASSED** |
| **Long OTM** | 794 | 8.0 | 0.851563 | 0.851602 | 0.851699 | 0.851740 | 0.000039 | 0.000136 | **0.000177 USD** | **PASSED** |
| **Long ATM** | 794 | 12.0 | 2.465211 | 2.465319 | 2.465473 | 2.465586 | 0.000109 | 0.000262 | **0.000375 USD** | **PASSED** |
| **Long ITM** | 794 | 17.0 | 5.607036 | 5.607259 | 5.607410 | 5.607641 | 0.000223 | 0.000374 | **0.000605 USD** | **PASSED** |
| **NU270617P17**| 212 | 17.0 | 4.762929 | 4.763247 | 4.762967 | 4.763302 | 0.000318 | 0.000037 | **0.000373 USD** | **PASSED** |

**Verificación Global en las 97 Puts:**
- Máxima discrepancia temporal: **$0.000397$ USD**
- Máxima discrepancia espacial: **$0.000282$ USD**
- Máxima discrepancia total vs Ultra-Fina: **$0.000605$ USD** (menos de un tercio del presupuesto de $0.0020$ USD).
- Número de opciones con desviación $> 0.0020$ USD: **0 de 97**.

### 2.4 Estabilidad de Clasificación y Evaluación en Malla Fina (Resolución F1-04)
Se reevaluó la función objetivo en Train (60 puts) para los 5 arranques comparando la malla dinámica de calibración ($tFactor=50.0$, mínimo $25$ pasos temporales $\implies t_{\text{steps}} = \max(25, \text{round}(50 \times T))$, $x=70, v=35$) frente a la malla fina de validación ($tFactor=200.0$, mínimo $25$ pasos temporales $\implies t_{\text{steps}} = \max(25, \text{round}(200 \times T))$, $x=200, v=100$), exportada en `data/heston/phase1/heston_multistart_fine_sse.csv`:

| Arranque | Nombre | SSE Calib ($tFactor50/x70/v35$) | RMSE Calib (USD) | SSE Fina ($tFactor200/x200/v100$) | RMSE Fina (USD) | Estado / Diagnóstico |
| :---: | :--- | :---: | :---: | :---: | :---: | :--- |
| **Start 1** | Canonical Skew | 0.088067 | 0.038312 | 0.088337 | 0.038370 | Cuasi-óptimo |
| **Start 2** | Positive Rho | **0.086649** | **0.038002** | **0.086762** | **0.038027** | **Mejor candidato encontrado entre los arranques predeclarados** |
| **Start 3** | High VolVol / Low Kappa | 0.586187 | 0.098842 | 21.468784 | 0.598175 | Sensibilidad numérica severa (Feller $\approx 0.0006$) |
| **Start 4** | Fast Mean Reversion | 0.089044 | 0.038523 | 0.089482 | 0.038618 | Cuasi-óptimo (Status 2 / No convergente) |
| **Start 5** | Zero Correlation | 0.087792 | 0.038252 | 0.087917 | 0.038279 | Cuasi-óptimo |

El orden relativo de los candidatos cuasi-óptimos se mantiene estrictamente estable entre mallas, confirmando la selección de **Start 2** como el mejor candidato encontrado sin requerir reoptimización heurística. Start 3 exhibe alta sensibilidad numérica al refinarse la discretización, quedando descartado. La evaluación en malla fina sirve como diagnóstico independiente de estabilidad numérica y equifinalidad paramétrica, mientras que la selección se realiza sobre el menor objetivo verificado entre los candidatos que convergieron con éxito (`status == 0`).

---

## 3. Resolución F1-02: Reconciliación 100% Documental y Dispersión Predictiva

### 3.1 Tabla por Tenor Reconciliada (Recuentos y Métricas Exactas del CSV)
Todas las cifras provienen directamente de `data/heston/phase1/heston_pricing_by_tenor.csv`:

| Vencimiento | Tenor (días) | N Contratos | Precio Medio Mkt | Precio Medio Heston | MAE (USD) | RMSE (USD) | Error Máximo (USD) | Prima Ejercicio Temprano ($P^{Am} - P^{Eu}$) |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **2026-11-20** | 3.0 | **12** | 2.2667 | 2.2417 | 0.0258 | 0.0300 | 0.0600 | 0.002582 USD |
| **2026-11-27** | 10.0 | **6** | 0.2550 | 0.2544 | 0.0124 | 0.0158 | 0.0252 | 0.000595 USD |
| **2026-12-04** | 17.0 | **8** | 0.6188 | 0.6094 | 0.0110 | 0.0133 | 0.0242 | 0.002766 USD |
| **2026-12-11** | 24.0 | **9** | 0.6600 | 0.6455 | 0.0213 | 0.0254 | 0.0493 | 0.003795 USD |
| **2026-12-18** | 31.0 | **8** | 1.3663 | 1.3424 | **0.0246** | 0.0342 | 0.0800 | **0.013734 USD** |
| **2026-12-24** | 37.0 | **7** | 0.4229 | 0.4257 | 0.0119 | 0.0140 | 0.0225 | 0.002028 USD |
| **2026-12-31** | 44.0 | **5** | 0.5800 | 0.6122 | 0.0322 | 0.0362 | 0.0610 | 0.003441 USD |
| **2027-01-15** | 59.0 | **7** | 1.6600 | 1.6545 | 0.0317 | 0.0438 | 0.1004 | 0.026293 USD |
| **2027-02-19** | 94.0 | **5** | 1.0240 | 1.0058 | 0.0210 | 0.0238 | 0.0407 | 0.011382 USD |
| **2027-03-19** | 122.0 | **5** | 1.2780 | 1.2717 | 0.0250 | 0.0284 | 0.0446 | 0.019503 USD |
| **2027-04-16** | 150.0 | **2** | 0.9200 | 0.9183 | 0.0037 | 0.0041 | 0.0054 | 0.011413 USD |
| **2027-06-17** | 212.0 | **7** | 2.0686 | 2.0757 | 0.0518 | 0.0755 | 0.1823 | 0.061010 USD |
| **2027-09-17** | 304.0 | **3** | 1.9600 | 1.9206 | 0.0394 | 0.0456 | 0.0714 | 0.064409 USD |
| **2027-12-17** | 395.0 | **3** | 3.5000 | 3.4933 | 0.0166 | 0.0173 | 0.0233 | **0.220507 USD** |
| **2028-01-21** | 430.0 | **5** | 1.5420 | 1.5286 | 0.0325 | 0.0373 | 0.0542 | 0.068226 USD |
| **2029-01-19** | 794.0 | **5** | 1.5700 | 1.5822 | 0.0122 | 0.0175 | 0.0295 | 0.111252 USD |

*(Total de opciones verificado: 97 contratos exactos. Fechas a 3d: 12 puts; a 794d: 5 puts; EEP a 31d: 0.0137 USD; EEP a 395d: 0.2205 USD).*

### 3.2 Análisis de Dispersión Predictiva entre Candidatos Cercanos
Para diagnosticar con rigor científico la identificación paramétrica en lugar de asumir "identificación perfecta", se analizaron los cuatro candidatos cuasi-óptimos cuyos objetivos se encuentran dentro del 5% del mínimo (Starts 1, 2, 4 y 5):
- En el corto plazo ($K=12, 31$d), los precios coinciden estrechamente: rango $[0.450495, 0.454464] \implies \Delta = 0.003968$ USD (~$0.4$¢).
- En el largo plazo extremo ($K=17, 794$d, LEAPS ITM profundo), los precios muestran dispersión: rango $[5.590467, 5.635634] \implies \Delta = \mathbf{0.045167}$ USD (~$4.5$¢).
- En el extremo ITM profundo ($K=30, 794$d, donde $K=30 \gg S_0 \approx 12.33$), el valor de ejercicio inmediato absorbe la varianza del modelo ($P \approx K - S_0$): rango $< 10^{-6}$ USD.

**Conclusión Metodológica:** La equifinalidad en el valle de parámetros $(\kappa, \xi)$ produce un calce in-sample prácticamente idéntico, pero genera una dispersión predictiva extrapolada de hasta $4.5$¢ en contratos LEAPS lejanos. Este comportamiento representa una limitación intrínseca de identificación bajo calibración puramente cross-sectional de opciones vanilla, que se reporta con rigor y transparencia sin recurrir a restricciones artificiales no fundamentadas.

---

## 4. Resolución F1-03: Precios Crudos, No Arbitraje y Diagnósticos Económicos

### 4.1 Evaluación Cruda sin Clipping
Se modificó `src/heston/heston_model.py` para desactivar el clipping artificial (`clip_to_intrinsic=False`, `clip_nonnegative=False`). Todos los diagnósticos de cotas se evaluaron sobre los valores directos del operador FDM:
- **Cota inferior de valor intrínseco:** $P_{\text{raw}} \ge \max(0, K - S_0) - 10^{-6}$ se cumple en el **100% de las 97 puts** (mínimo gap $= 0.000000$ USD).
- **Cota superior:** $P_{\text{raw}} \le K$ se cumple en el **100% de las 97 puts**.
- **Prima de ejercicio temprano:** $P_{\text{raw}}^{Am} \ge P_{\text{raw}}^{Eu} - 10^{-5}$ se cumple en el **100% de las 97 puts**.

### 4.2 Convexidad en Strike por Segundas Diferencias Divididas
Para mallas de strikes no uniformes $K_{i-1} < K_i < K_{i+1}$, se implementó la segunda diferencia dividida:
$$\mathcal{D}^2 P(K_i) = 2 \cdot \frac{\frac{P(K_{i+1}) - P(K_i)}{K_{i+1} - K_i} - \frac{P(K_i) - P(K_{i-1})}{K_i - K_{i-1}}}{K_{i+1} - K_{i-1}}$$
- **Puntos interiores:** Se requiere $\mathcal{D}^2 P \ge -0.0020$. Se verificó que el **100% de los puntos interiores cumplen la condición** (`convexity_status == "PASS"`).
- **Puntos de frontera ($i=0, i=N-1$):** Se registran rigurosamente como `NOT_TESTABLE`, evitando aprobaciones vacías por defecto.

### 4.3 Monotonía Temporal a Strike Fijo
Para una opción put americana sobre un activo sin dividendos ($q=0$), el derecho de ejercicio anticipado garantiza teóricamente que $P(K, T_2) \ge P(K, T_1)$ para $T_2 > T_1$. Se evaluaron **todas las 75 transiciones temporales** correspondientes a los 14 strikes que cotizan en múltiples vencimientos:
- Número de transiciones conformes ($P(T_2) - P(T_1) \ge -0.0020$): **75 de 75 (100%)**.
- Violaciones de monotonía temporal: **0**.

### 4.4 Esquemas Numéricos y Motores Empleados
1. **Esquema ADI en QuantLib (`FdHestonVanillaEngine`):**
   Implementa un esquema de direcciones alternadas implícitas (ADI) con configuración por defecto de Hundsdorfer (`FdmSchemeDesc::Hundsdorfer()`) para ecuaciones parabólicas bidimensionales con término cruzado de covarianza $\rho \xi v S \frac{\partial^2 V}{\partial S \partial v}$, aplicando proyección libre sobre el obstáculo de ejercicio americano en cada paso de tiempo.
2. **Integración Semi-analítica (`AnalyticHestonEngine`):**
   Utiliza la representación analítica de la función característica de Heston (Heston 1993, formulación de logaritmo complejo continuo de Albrecher et al. 2007) invocando directamente el constructor `AnalyticHestonEngine(model)` de QuantLib, cuyo orden de integración por defecto es fijo (`integrationOrder = 144`). No se emplean tolerancias adaptativas relativas ni algoritmos adicionales de cuadratura sobre este motor analítico.

---

## 5. Comparativa en Muestra Común (84 Puts) frente a SVI y Baseline Plano

Todas las métricas coinciden exactamente con `data/heston/phase1/heston_common_84_comparison.csv`:

| Modelo Evaluado | Curva Consumida | MAE (USD) | RMSE (USD) | Error Máximo (USD) |
| :--- | :--- | :---: | :---: | :---: |
| **Heston Clásico (Fase 1 Remediada)** | **Oficial CMT Bootstrap (Densa)** | **0.0232 USD** (0.023158) | **0.0339 USD** (0.033921) | **0.1823 USD** (0.182281) |
| **Baseline Flat American** | Oficial CMT Bootstrap (Densa) | **0.0397 USD** (0.039674) | **0.0603 USD** (0.060289) | **0.3333 USD** (0.333314) |
| **SVI Histórico (`m4_am_surf`)** | Par Conversion R3 (11/18 mezclado) | **0.0684 USD** (0.068442) | **0.0886 USD** (0.088579) | **0.2463 USD** (0.246300) |

Heston clásico con 5 parámetros globales reduce el error medio de SVI histórico en un **66%** ($0.0684 \to 0.0232$ USD) y el del baseline plano en un **42%** ($0.0397 \to 0.0232$ USD). El error máximo del baseline plano ($0.3333$ USD) frente al de Heston ($0.1823$ USD) refleja la incapacidad de una superficie plana para acomodar la curvatura de volatilidad implícita en las colas.

---

## 6. Trazabilidad Criptográfica, Validación de Caché y Artefactos Publicados

### 6.1 Validación Criptográfica Estricta de Caché y Replay (Resolución F1-04)
El pipeline en `src/heston/pipeline_phase1.py` incorpora una función de validación criptográfica (`validate_and_load_multistart_cache`) que erradica la aceptación ciega de archivos preexistentes:
1. **Comprobación Criptográfica de Insumos:** Calcula los hashes SHA-256 de todos los datos de entrada (`data_split_train.csv`, `treasury_cmt_2026_11_17_raw.json`, etc.) y los compara contra los registrados en `phase1_execution_manifest.json`. Si cualquiera difiere, la caché se descarta y exige recálculo.
2. **Validación Estricta de Parámetros y Consistencia Matemática:** Se verifica la presencia del esquema completo, la finitud y cotas físicas de todos los parámetros ($v_0, \kappa, \theta, \xi > 0$, $|\rho| < 1$), y la no negatividad matemática y finitud estricta de la pérdida y RMSE ($SSE \ge 0$, $\text{RMSE} \ge 0$, rechazando valores $\text{NaN}$ o $\pm\infty$).
3. **Replay Numérico Incondicional del Objetivo:** Se evalúa obligatoriamente la función de pérdida sobre los 60 contratos de Train para **la totalidad de los 5 arranques** ($i=1..5$) en la malla de calibración ($tFactor=50.0, x=70, v=35$). Ningún candidato queda exento de validación por su estado o pérdida declarada.
4. **Tolerancia Determinista de Replay:** La tolerancia entre la SSE serializada en CSV y la revaluada se fija en $10^{-4}$ $\text{USD}^2$ (unidades de pérdida cuadrática). Dado que el solver FDM es determinista, la discrepancia observada entre parámetros serializados y revaluados es puramente de redondeo numérico de punto flotante en almacenamiento ($\approx 10^{-13}$ $\text{USD}^2$).
5. **Regla de Elegibilidad para Selección:** Solo los candidatos con convergencia exitosa (`status == 0`) son elegibles como modelo operativo, seleccionando entre ellos el de menor pérdida verificada (**Start 2**). Los candidatos con terminación anómala (e.g. Start 4 con `status == 2`) se conservan en la tabla multistart para registro académico pero son explícitamente inelegibles.
6. **Malla Fina de Diagnóstico:** Se calcula y persiste la tabla de SSE en resolución fina ($tFactor=200.0, x=200, v=100$) en `heston_multistart_fine_sse.csv`. La malla fina actúa como diagnóstico independiente de estabilidad numérica y equifinalidad.
7. **Cobertura con Tests Negativos:** En `tests/test_heston_phase1.py` se validan 6 pruebas negativas que aseguran el fallo inmediato ante datos de entrenamiento alterados, SSE negativo, parámetros fuera de cotas, candidatos no convergentes con SSE falsificada a cero (contraejemplo Codex status 2 / SSE 0), RMSE con $\text{NaN}$ o $\pm\infty$, y discrepancias entre SSE declarada y objetivo reevaluado.

### 6.2 Artefactos Publicados en Repositorio
Todos los artefactos se encuentran depositados exclusivamente en `data/heston/phase1/` con enlaces relativos para accesibilidad en el repositorio:
- [`phase1_execution_manifest.json`](../../data/heston/phase1/phase1_execution_manifest.json): Manifiesto con timestamps disociados, hashes de insumos, versiones y diagnóstico integral de gate.
- [`heston_multistart_results.csv`](../../data/heston/phase1/heston_multistart_results.csv): Registro de los 5 arranques con tipo de terminación explícita (`CONVERGED`, `MAX_ITERATIONS`, etc.).
- [`heston_multistart_fine_sse.csv`](../../data/heston/phase1/heston_multistart_fine_sse.csv): Evaluación del objetivo en malla fina ($tFactor=200.0, x=200, v=100$).
- [`heston_candidate_predictive_dispersion.csv`](../../data/heston/phase1/heston_candidate_predictive_dispersion.csv): Rango predictivo de candidatos cercanos.
- [`heston_pricing_train.csv`](../../data/heston/phase1/heston_pricing_train.csv): Precios crudos y errores en Train (60 puts).
- [`heston_pricing_strike_holdout.csv`](../../data/heston/phase1/heston_pricing_strike_holdout.csv): Evaluación en Strike Holdout (22 puts).
- [`heston_pricing_tenor_holdout.csv`](../../data/heston/phase1/heston_pricing_tenor_holdout.csv): Evaluación en Tenor Holdout (15 puts).
- [`heston_pricing_full_puts.csv`](../../data/heston/phase1/heston_pricing_full_puts.csv): Precios crudos en las 97 puts con brechas de cotas.
- [`heston_pricing_by_tenor.csv`](../../data/heston/phase1/heston_pricing_by_tenor.csv): Estadísticas agregadas reconciliadas al 100%.
- [`heston_calls_contrast.csv`](../../data/heston/phase1/heston_calls_contrast.csv): Evaluación en 142 calls de contraste.
- [`heston_common_84_comparison.csv`](../../data/heston/phase1/heston_common_84_comparison.csv): Comparación en los 84 contratos comunes frente a SVI y Flat.
- [`heston_grid_convergence.csv`](../../data/heston/phase1/heston_grid_convergence.csv): Refinamientos separados (temporal, espacial, ultra-fina).
- [`heston_shape_arbitrage_checks.csv`](../../data/heston/phase1/heston_shape_arbitrage_checks.csv): Cotas crudas, monotonía en strike y diferencias divididas en los 16 tenors.
- [`heston_tenor_monotonicity_checks.csv`](../../data/heston/phase1/heston_tenor_monotonicity_checks.csv): 75 transiciones a strike fijo.
- [`heston_phase1_summary.csv`](../../data/heston/phase1/heston_phase1_summary.csv): Tabla ejecutiva de criterios de gate.

---

## 7. Conclusión y Recomendación

La Remediación 3 de la Fase 1:
1. **Unifica y valida la malla productiva** (`300x160x80`), demostrando que el error de discretización espacial y temporal conjunto es $\le 0.000605$ USD en el conjunto evaluado (plenamente inferior al presupuesto de $0.0020$ USD).
2. **Implementa validación criptográfica y replay incondicional de caché (F1-04)** sobre todos los candidatos en la malla de calibración ($tFactor=50, x=70, v=35$) con tolerancia determinista de $10^{-4}$ $\text{USD}^2$, regla de elegibilidad estricta para candidatos convergentes (`status == 0`), verificación de finitud en RMSE (rechazando $\text{NaN}/\pm\infty$) y exportación de evaluación en malla fina (`heston_multistart_fine_sse.csv`), respaldada por una suite exhaustiva de tests negativos.
3. **Reconcilia al 100% todas las especificaciones numéricas y documentales (F1-02)**, precisando la parametrización de mallas dinámicas ($tFactor50$ y $tFactor200$), la fórmula de covarianza cruzada en la PDE ($\rho \xi v S \frac{\partial^2 V}{\partial S \partial v}$), la firma exacta de los motores QuantLib (`FdmSchemeDesc::Hundsdorfer()` e `AnalyticHestonEngine` con orden fijo 144), las métricas de la muestra común (84 puts), la caracterización de $K=30$ como ITM profundo y la delimitación de ausencia de arbitraje a resultados numéricos sobre la muestra observada.
4. **Verifica la ausencia de violaciones de cotas y no arbitraje en la muestra observada sobre precios crudos sin clipping**, aprobando la totalidad de las pruebas de cotas, monotonía en strike, monotonía temporal y convexidad por diferencias divididas dentro de las tolerancias numéricas establecidas ($\le 0.0020$ USD).

Se dictamina **cumplimiento cuantitativo, formal, computacional y metodológico pleno del Gate PoC de Fase 1**, quedando el código listo para la auditoría técnica independiente definitiva de Codex previa a la Fase 2.
