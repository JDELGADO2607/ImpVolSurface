# Registro Vivo de Decisiones Metodológicas y Limitaciones del Proyecto

Este documento registra formalmente cada decisión de diseño cuantitativo, financiero y computacional adoptada a lo largo del proyecto, contrastándola con las alternativas evaluadas, los motivos técnicos de la elección, la evidencia cuantitativa obtenida y las limitaciones residuales.

---

## 1. Registro Sistemático de Decisiones

### DEC-001: Selección del Estado de Mercado Base y Fecha de Valoración
* **Decisión:** Fijar la fecha y hora de referencia para el caso base en el **17 de noviembre de 2026 a las 16:00 EST (America/New_York)**, con un precio spot de cierre de **$S_0 = 12.33$ USD**.
* **Alternativas evaluadas:**
  1. Utilizar la fecha y hora de descarga del archivo Excel (18 de noviembre de 2026, 09:52 COT / 09:52 EST).
  2. Ajustar el spot a cada transacción individual según la marca de tiempo de `lastTradeDate`.
* **Motivo de la elección:** La inspección forense de los 575 contratos demostró que **cero contratos transaron el 18 de noviembre**. Los 291 contratos más líquidos transaron durante la sesión del 17 de noviembre, culminando exactamente a las 15:59:55 EST. Asignar como fecha de valoración el 18 de noviembre cuando los precios provienen del 17 de noviembre introduciría una asincronía artificial de casi 1 día entero que distorsionaría severamente las madureces cortas (por ejemplo, el vencimiento del 20 de noviembre pasaría de 3 días a 2 días, un error de tiempo del 33%).
* **Evidencia:** Registro histórico de Yahoo Finance y NYSE confirma que NU cerró el 17-nov en $12.33 USD (High: 12.83, Low: 12.24, Open: 12.73). El 18-nov abrió en 12.33 y cayó a 12.08.
* **Limitaciones:** Los 284 contratos con última transacción anterior al 17 de noviembre arrastran un desfase temporal respecto a $S_0 = 12.33$. Dichos contratos deben ser identificados y clasificados en niveles de menor confianza (Tiers 3 y 4).

### DEC-002: Descarte del Filtro `bid > 0` y Selección de la Fuente de Precio de Mercado
* **Decisión:** Utilizar como precio objetivo observado $P_{\text{obs}}$ la columna `lastPrice` del 17 de noviembre, sujeta a filtros rigurosos de cotas económicas de no arbitraje y valor tiempo mínimo ($TV \ge 0.01$). Descartar el filtro ingenuo `bid > 0`.
* **Alternativas evaluadas:**
  1. Exigir `bid > 0` y usar `midPrice = (bid + ask) / 2`.
  2. Usar las volatilidades nativas de Yahoo Finance (`impliedVolatility`).
  3. Calibrar directamente contra Bloomberg `IV Mid`.
* **Motivo de la elección:** En el archivo, 538 de los 575 contratos (93.57%) presentan `bid = 0` y `ask = 0` debido a que Yahoo Finance resetea las cotizaciones bilaterales tras el cierre. Exigir `bid > 0` destruiría el 94% de la muestra y dejaría únicamente 32 contratos con cotizaciones obsoletas de hace meses. Por su parte, la `impliedVolatility` de Yahoo presenta valores espurios de $10^{11}$ y patrones diádicos, mientras que calibrar contra Bloomberg violaría la instrucción central de que nuestra superficie provenga exclusivamente de nuestro propio motor numérico.
* **Evidencia:** Análisis forense en `outputs/data_diagnostics/dump_Hoja1.csv`.
* **Limitaciones:** `lastPrice` incorpora el rebote de la última transacción entre el bid y el ask (bid-ask bounce). Por ende, se exige un condicionamiento numérico $\kappa = 0.01 / \text{Vega}$ para asegurar que un error de un centavo no distorsione la volatilidad implícita en más de 3 puntos porcentuales.

### DEC-003: Recálculo Exacto de la Madurez Temporal $\tau$
* **Decisión:** Calcular la madurez en años $\tau$ bajo la convención **Act/365F continuo**, midiendo el tiempo exacto en días calendario desde el cierre del 17-nov-2026 (16:00 EST) hasta las 16:00 EST de la fecha de vencimiento contractual.
* **Alternativas evaluadas:**
  1. Conservar la columna `yearsToExpiry` del Excel.
  2. Dividir por 360 o contar días hábiles (Bus/252).
* **Motivo de la elección:** La columna `yearsToExpiry` del Excel sufre dos defectos críticos: 77 filas están corruptas por escala de localización ($10^{16}$) y las restantes sufrieron un truncamiento a días enteros a medianoche ($\lfloor T - t \rfloor / 365.25$). Esto reducía el plazo del primer vencimiento de 3 días a 1 día, introduciendo un sesgo de subestimación del -55.7% en $\tau$ y duplicando artificialmente la volatilidad implícita. En derivados sobre acciones de EE.UU., el estándar contractual del OCC descuenta el tiempo continuo calendario (Act/365).
* **Evidencia:** Comparación directa entre $\tau_{\text{recalculado}}$ y `yearsToExpiry`.

### DEC-004: Arquitectura de Valoración Diferenciada (Calls vs Puts sin Dividendos)
* **Decisión:** Valorar opciones Call americanas mediante la fórmula analítica cerrada de Black-Scholes para opciones europeas ($q = 0, r \ge 0$). Valorar opciones Put americanas mediante Diferencias Finitas (Crank-Nicolson con suavizado de Rannacher y método de penalización).
* **Alternativas evaluadas:**
  1. Resolver la EDP de diferencias finitas tanto para Calls como para Puts.
  2. Utilizar el árbol de Cox-Ross-Rubinstein (CRR) para todas las opciones.
* **Motivo de la elección:** Es un teorema fundamental de no arbitraje (Merton, 1973) que para una opción Call americana sobre una acción que no paga dividendos ($q = 0$) y con tasas de interés no negativas ($r \ge 0$), el ejercicio anticipado nunca es óptimo antes del vencimiento, de modo que $C_{\text{American}}(S, K, \tau) \equiv C_{\text{European}}(S, K, \tau)$. La solución analítica de Black-Scholes es exacta, libre de error de discretización y computacionalmente instantánea ($1000\times$ más rápida). Por el contrario, en las Puts americanas el ejercicio anticipado sí puede ser óptimo para cobrar el strike $K$ y generar intereses, requiriendo resolver la frontera libre mediante Crank-Nicolson + Penalización. CRR se mantiene como validador numérico de convergencia independiente.
* **Evidencia:** Demostración matemática detallada en el Manual Matemático y pruebas unitarias de convergencia.

### DEC-005: Algoritmo de Inversión de Volatilidad Implícita (Brent vs Newton)
* **Decisión:** Implementar el algoritmo de Brent sobre el intervalo de búsqueda $\sigma \in [0.01, 5.00]$ con tolerancia absoluta de precio de $10^{-6}$ USD.
* **Alternativas evaluadas:**
  1. Newton-Raphson estándar: $\sigma_{n+1} = \sigma_n - \frac{f(\sigma_n)}{\nu(\sigma_n)}$.
  2. Bisección pura.
* **Motivo de la elección:** Newton-Raphson diverge o da pasos descontrolados cuando la opción está profundamente OTM o ITM, ya que la Vega $\nu \to 0$, haciendo que el denominador tienda a cero. Brent combina interpolación cuadrática inversa, secante y bisección garantizada, asegurando convergencia superlineal cuando el comportamiento es suave y convergencia garantizada en el bracket sin riesgo de división por cero.
* **Evidencia:** Pruebas de recuperación de volatilidad sintética en `tests/test_iv_recovery.py`.

### DEC-006: Estabilización de Griegas Numéricas Americanas Mediante Dominio Fijo $S_{\max}$ y Malla Compartida PCHIP
* **Decisión:** Fijar un dominio espacial común e invariante $S_{\max} = 4.0 \cdot \max(S_0, K)$ para evaluar el precio base y los puntos perturbados $S_0 \pm dS$. Evaluar las perturbaciones sobre la misma solución discreta EDP mediante interpolación local monótona PCHIP en lugar de reconstruir tres mallas independientes con splines cúbicos oscilatorios.
* **Alternativas evaluadas:**
  1. Mantener $S_{\max}(S) = 4.0 \cdot \max(S, K)$ recalculado dinámicamente para cada bump.
  2. Aumentar arbitrariamente el bump $dS$ a $0.10$ o $0.50$ para tapar el ruido numérico.
  3. Sustituir el Gamma americano por el Gamma europeo analítico de Black-Scholes.
* **Motivo de la elección:** Al perturbar el spot con $S_{\max}$ dependiente de $S$, se generaban tres mallas desalineadas. El error de interpolación cúbica $O(\Delta S^2)$, al dividirse por $dS^2 = 10^{-4}$, se amplificaba 10,000 veces, disparando el Gamma de la Put $K=12$ a un absurdo $3.3547$. La fijación de $S_{\max}$ y el uso de PCHIP local suprimen por completo el ruido de malla y devuelven un Gamma estable y económicamente riguroso de $0.2375$, consistente a través de bumps $dS \in [0.005, 0.05]$ y resoluciones $M \in [150, 900]$.
* **Evidencia:** Pruebas de regresión parametrizadas en `tests/test_pde_greeks_stability.py`.

### DEC-007: Eliminación Estricta del Sesgo de Anticipación en HAR-RV Mediante Walk-Forward Purificado
* **Decisión:** Implementar una validación econométrica fuera de muestra estrictamente purificada (*purged walk-forward*), restringiendo la muestra de entrenamiento para pronosticar en la fecha $t$ a observaciones históricas estrictamente anteriores a $s \le t - 21$.
* **Alternativas evaluadas:**
  1. Entrenar con toda la muestra histórica disponible hasta la fecha $t$ (`iloc[:t]`).
  2. Ajustar un único modelo estático in-sample para toda la serie.
* **Motivo de la elección:** Debido a que el objetivo dependiente $RV_{t, t+21}^{(m)}$ es un promedio rodante de varianza que se proyecta 21 días hacia el futuro, entrenar con observaciones entre $t-20$ y $t-1$ utiliza etiquetas que contienen datos contemporáneos a la ventana proyectada, induciendo una fuga de información (*target leakage*). La purga estricta ($s \le t - 21$) garantiza ortogonalidad temporal absoluta. Bajo este esquema, HAR-RV demostró superioridad predictiva genuina con una pérdida QLIKE de $0.1855$, batiendo a EWMA ($0.2099$) y a la volatilidad histórica ($0.2512$).
* **Evidencia:** Prueba de invariancia contrafactual en `tests/test_no_lookahead.py` y tabla `outputs/tables/volatility_forecast_evaluation.csv`.

### DEC-008: Unificación Contable del Stress Testing y Adopción de Margen Regulatorio como Capital Económico
* **Decisión:** Separar algebraicamente la discrepancia inicial de marca a modelo ($\Pi_{0,\text{model}} - \Pi_{0,\text{market}} = -\$20.43$ USD) del P&L generado por los shocks de estrés ($\Pi_{1,\text{model}} - \Pi_{0,\text{model}}$). Incorporar el Escenario Nulo (S0) como prueba diagnóstica y definir el denominador de rentabilidad mediante el requerimiento prudencial de margen regulatorio (Reg T / FINRA 4210) de $\$5\,435.31$ USD.
* **Alternativas evaluadas:**
  1. Restar el precio de mercado inicial del precio del modelo estresado final.
  2. Sumar el valor absoluto de pasivos cortos y acciones cortas como "capital invertido".
  3. Mantener la afirmación de que la discrepancia de Taylor era de $-\$3\,253$ USD.
* **Motivo de la elección:** Mezclar la marca inicial con la respuesta al shock contaminaba la medición de riesgo con el error de modelo en $t_0$. En carteras con posiciones cortas, sumar el valor absoluto de pasivos no representa capital propio sino apalancamiento bruto. Al limpiar la contabilidad e introducir Griegas estabilizadas, el Escenario Nulo produce P&L idénticamente nulo ($0.00$ USD), la suma de patas reconcilia exactamente con el total del portafolio, y la discrepancia de Taylor en Crisis Severa se desmitifica: se reduce de $-\$3\,253$ USD a $-\$261.15$ USD, demostrando que gran parte de la brecha anterior era ruido numérico y no hiper-no-linealidad financiera.
* **Evidencia:** `tests/test_portfolio_and_stress.py` y `outputs/tables/stress_test_matrix.csv`.

### DEC-009: Restricciones Robustas de Roger Lee y Proyección Monótona de Calendario en SVI
* **Decisión:** Imponer la cota analítica de momentos de Roger Lee $b(1+|\rho|) \le 1.95 < 2.0$ y la penalización estricta de densidad neutral al riesgo $g(k) \ge 0$ al 100% de la malla empírica. Si un vencimiento tiene menos de 6 strikes, activar la política conservadora de Fallback por Spline PCHIP monótono.
* **Alternativas evaluadas:**
  1. Calibrar SVI con cotas laxas ($b(1+|\rho|) < 4.0$) sobre madureces con 2 a 5 contratos.
  2. Tolerar hasta un 20% de violaciones mariposa fuera de dinero.
* **Motivo de la elección:** Ajustar 5 parámetros SVI sobre 2 a 5 observaciones está matemáticamente subidentificado y genera curvaturas extremas en las alas no observadas. La condición $b(1+|\rho|) < 2.0$ es indispensable para evitar densidades con colas más pesadas que las permitidas por la física neutral al riesgo ($\mathbb{E}[S_T] < \infty$).
* **Evidencia:** `tests/test_surface_and_interpolation.py` y tabla `outputs/tables/svi_slice_parameters.csv`.

### DEC-010: Evaluación Temporal Unificada y Eliminación de Discontinuidades en Nodos Calibrados (Segunda Ronda)
* **Decisión:** Unificar la evaluación temporal de la superficie para cualquier $\tau$ imponiendo la secuencia proyectada acumulativa monótona $w^*(\tau_i, k) = \max_{j \le i} w_{\text{raw}}(\tau_j, k)$ tanto en los nodos exactos $\tau = \tau_i$ como en la interpolación intermedia $C^1$ mediante PCHIP en $\tau$, junto con extrapolaciones planas continuas en volatilidad implícita para $\tau < \tau_1$ y $\tau > \tau_N$.
* **Alternativas evaluadas:**
  1. Evaluar el corte crudo $w_{\text{raw}}(\tau_i, k)$ cuando $\tau$ coincide con un tenor calibrado, y aplicar `maximum.accumulate` solo en puntos interpolados.
  2. Forzar un ajuste global bidimensional no lineal de SVI paramétrico simultáneo (Surface SVI).
* **Motivo de la elección:** La alternativa 1 provocaba una inconsistencia matemática severa: decrementos de varianza total exactamente en los nodos originales (Casos A y B de la auditoría) y un salto artificial discontinuo al aproximarse al tenor desde la izquierda o derecha ($\lim_{\epsilon \to 0} w(\tau_i \pm \epsilon) \neq w(\tau_i)$). La alternativa 2 introduce rigidez excesiva y distorsiona el ajuste de los strikes líquidos. La evaluación unificada garantiza $w(k, \tau_2) \ge w(k, \tau_1)$ para todo $\tau_2 \ge \tau_1 \ge 0$, elimina saltos de interpolación ($|\text{salto}| < 10^{-6}$), preserva la positividad de la varianza total y registra con precisión trazable los ajustes introducidos.
* **Evidencia:** Eliminación de los contraejemplos Casos A y B en `tests/test_surface_and_interpolation.py`, verificación de continuidad $C^1$ y registro en `outputs/tables/svi_slice_parameters.csv`.

### DEC-011: Validación Económica Explícita de Cortes Fallback PCHIP sin Garantías Ficticias (Segunda Ronda)
* **Decisión:** Erradicar la asignación automática de `pct_no_butterfly_arb = 100.0%` en cortes fallback generados por PCHIP, reportando explícitamente `NaN` para la fórmula analítica $g(k)$ de SVI y sustituyéndola por una validación transversal exhaustiva basada en diferencias divididas de convexidad de precios ($\frac{\Delta^2 C}{\Delta K^2} \ge -\text{tol}$), límites intrínsecos y monotonía empírica.
* **Alternativas evaluadas:**
  1. Aplicar la función analítica $g(k)$ de Raw SVI a la curva PCHIP.
  2. Declarar 100% de no arbitraje asumiendo que PCHIP preserva forma por diseño.
* **Motivo de la elección:** La función analítica $g(k)$ se deriva matemáticamente de la primera y segunda derivada de la hipérbola Raw SVI; aplicarla a un spline por tramos carece de rigor formal. Asimismo, PCHIP preserva la monotonicidad de los datos empíricos de varianza, pero no garantiza automáticamente la convexidad de los precios de las opciones respecto al strike. Al evaluar numéricamente la convexidad, se descubrió que los vencimientos de 3d y 395d cumplen 100% de convexidad, mientras que el corte LEAPS de enero de 2029 (794d) exhibe anomalías en el strike extremo $K=3.0$ debido a iliquidez del mercado. Este hecho se registra de forma transparente como `EMPIRICAL_ANOMALIES_DETECTED` en lugar de enmascararlo con una garantía ficticia.
* **Evidencia:** Metadatos ampliados en `svi_slice_parameters.csv` y prueba `test_pchip_fallback_economic_validation_and_no_fictitious_guarantees`.

### DEC-012: Vinculación Estricta entre Señal Causal y Posiciones Simuladas del Portafolio (Segunda Ronda)
* **Decisión:** Desacoplar la generación de señales de la evaluación de cartera y condicionar la apertura real de posiciones en la simulación académica al valor de la señal:
  - `LONG_VOLATILITY_STRADDLE`: abre $+1$ Call, $+1$ Put, cobertura corta de acciones, fricciones y P&L de straddle largo.
  - `NO_TRADE`: establece exactamente $0.0$ contratos, $0$ acciones, $\$0.00$ de fricción y $\$0.00$ de P&L bajo todos los escenarios de estrés, con justificación explícita de neutralidad.
  - `SHORT_VOLATILITY_STRADDLE`: abre $-1$ Call, $-1$ Put, cobertura larga de acciones, recolecta prima inicial y asume pérdidas de cola no acotadas, etiquetado formalmente como `THEORETICAL_SHORT_STRADDLE_UNBOUNDED_TAIL_RISK`.
* **Alternativas evaluadas:**
  1. Generar la señal como etiqueta descriptiva y evaluar siempre el payoff de un straddle largo.
  2. Forzar artificialmente una señal positiva mediante la alteración de umbrales para conservar el resultado anterior.
* **Motivo de la elección:** La señal cuantitativa no puede ser cosmética; cambiar el pronóstico debe transformar las posiciones y el P&L simulado. La política respeta el resultado empírico causal (con el pronóstico purificado de 72.97% se activa `LONG_VOLATILITY_STRADDLE`), pero responde dinámicamente si se somete a pronósticos neutros o bajistas.
* **Evidencia:** Pruebas parametrizadas en `tests/test_no_lookahead.py`.

### DEC-013: Propagación Bloqueante de Errores y Códigos de Salida en el Pipeline (`run_all.py`) (Segunda Ronda)
* **Decisión:** Configurar el orquestador maestro `run_all.py` para validar exhaustivamente la existencia, integridad y finitud de los artefactos generados tras cada etapa, deteniendo el flujo inmediatamente ante excepciones en etapas críticas y propagando códigos de salida distintos de cero (`sys.exit(code)`) ante cualquier fallo de pruebas o validaciones.
* **Alternativas evaluadas:**
  1. Imprimir advertencias en consola (`WARNING`) y continuar hasta anunciar éxito general con código 0.
  2. Omitir validaciones intermedias de tablas generadas.
* **Motivo de la elección:** Un pipeline financiero en producción cuantitativa no puede reportar éxito si existen pruebas unitarias fallidas o artefactos incompletos.
* **Evidencia:** Suite de pruebas en `tests/test_pipeline_error_propagation.py`.

### DEC-014: Armonización Global de Cortes y Eliminación de Convexidad Artificial por Proyección Puntual (Tercera Ronda)
* **Decisión:** Reemplazar la proyección monótona puntual `maximum.accumulate` en $k$ —la cual introducía pliegues de pendiente $C^0$ que desestabilizaban la curvatura transversal al interpolar temporalmente— por una armonización global del parámetro de nivel $a_i \leftarrow a_i + \Delta a_i$ entre cortes adyacentes sobre su soporte empírico compartido, combinada con interpolación lineal en varianza total por tramos entre vencimientos calibrados contiguos ($w(k, \tau) = (1-\lambda)w_1(k) + \lambda w_2(k)$).
* **Alternativas evaluadas:**
  1. Mantener PCHIP cúbico temporal con clipping puntual ad-hoc sobre precios.
  2. Interpolación afín en precios normalizados respecto al forward.
* **Motivo de la elección:** La interpolación lineal en varianza total entre cortes armonizados convexos preserva analíticamente la monotonía temporal estricta ($\frac{\partial w}{\partial \tau} \ge 0$), garantiza la convexidad estricta de precios de calls ($\frac{\partial^2 C}{\partial K^2} \ge 0$) al ser una combinación convexa de sonrisas libres de arbitraje, elimina por completo las concavidades demostradas en los contraejemplos de 27.5d y 612d, y preserva la suavidad $C^\infty$ en $k$.
* **Evidencia:** 100% de convexidad de precios verificada en `tests/test_surface_convexity_and_extrapolation.py` sobre mallas de 121, 241 y 481 strikes.

### DEC-015: Cuarentena Formal de Opciones LEAPS (Enero 2029) y Límite del Horizonte de Producción (Tercera Ronda)
* **Decisión:** Establecer el horizonte de producción de la superficie en $\tau \le 430.0$ días (21 de enero de 2028). Calibrar el corte LEAPS de enero de 2029 (794d) excluyendo la cotización anómala y asíncrona de la Call $K=3.0$ (volumen 1, IV 103.88% vs Put 52.31%), lo cual permite un ajuste SVI con RMSE de 1.00% y 100% libre de arbitraje mariposa, pero clasificar formalmente dicho corte como `QUARANTINED_LEAPS_EXPLORATORY_ONLY` (`is_production_ready: False`). Consultas en modo estricto (`policy='strict'`) que superen los 430 días son bloqueadas con excepción explícita.
* **Alternativas evaluadas:**
  1. Mantener el corte de 2029 dentro del núcleo de producción a pesar de la iliquidez de cotizaciones de LEAPS.
  2. Eliminar completamente el vencimiento de 2029 del dataset.
* **Motivo de la elección:** Permite conservar la información para análisis exploratorio y descriptivo sin arriesgar la integridad de la valoración del portafolio o de las estrategias de producción.
* **Evidencia:** Prueba `test_h2_jan_2029_svi_calibration_clean_and_quarantine_status`.

### DEC-016: Preservación de la Monotonicidad Temporal en Puts Americanas mediante Piso de Continuación (Tercera Ronda)
* **Decisión:** Incorporar una restricción de crecimiento mínimo de varianza total entre vencimientos adyacentes de producción ($w_2(k) \ge w_1(k) \cdot (\tau_2 / \tau_1)^{0.22}$) en regiones compartidas donde la varianza total casi plana inducía una caída artificial en el valor de continuación del put americano ($P(37\text{d}) < P(31\text{d})$ a $K=14.75$).
* **Alternativas evaluadas:**
  1. No intervenir la varianza total y atribuir la caída al efecto de tasas de interés o dividendos.
  2. Forzar un salto discreto solo en el strike $K=14.75$.
* **Motivo de la elección:** Con dividendo cero ($q=0$) y tasas constantes o moderadas, una opción americana debe ser monótona no decreciente respecto al plazo de vencimiento ($P(\tau_2) \ge P(\tau_1)$) debido al derecho de ejercicio anticipado. La amortiguación suave de nivel garantiza $P(37\text{d}) \ge P(31\text{d})$ sin introducir discontinuidades ni violaciones mariposa.
* **Evidencia:** Prueba `test_h5_american_put_time_monotonicity_31d_to_37d`.

### DEC-017: Aislamiento de Artefactos de Prueba y Contratos de Datos Formales (Tercera Ronda)
* **Decisión:** Implementar el parámetro `export_artifacts: bool = True` en los módulos de estrategias comerciales y aislar completamente la ejecución de pruebas unitarias y de estrés, impidiendo que corridas contrafactuales de pytest sobrescriban los archivos CSV y figuras de producción. Asimismo, implementar en `run_all.py` el diccionario `DATA_CONTRACTS` con validaciones de esquema, columnas requeridas, filas mínimas y finitud numérica para las 16 tablas del proyecto.
* **Alternativas evaluadas:**
  1. Restaurar los archivos de producción re-ejecutando etapas al final de la suite de pruebas.
  2. Validar únicamente la existencia de los archivos sin comprobar esquemas de columnas.
* **Motivo de la elección:** Las pruebas nunca deben contaminar el estado de producción de los artefactos publicados.
* **Evidencia:** Pruebas `test_production_artifacts_hash_invariance_codex_h4` y suite `test_pipeline_error_propagation.py`.

### DEC-018: Validación Cruzada Holdout 2D Integral (Tercera Ronda)
* **Decisión:** Reemplazar el estimador unidimensional de corte aislado por una validación cruzada Leave-One-Strike-Out verdaderamente bidimensional (`surface_final_holdout_validation.csv`): para cada par $(K_{\text{test}}, \tau_{\text{test}})$, se excluyen simultáneamente tanto la Call como la Put, se recalibra el corte, se armonizan los niveles de la superficie 2D, se evalúa en el motor de superficie bidimensional final y se valoran las opciones con el motor EDP americano (puts) y Black-Scholes cerrado (calls).
* **Alternativas evaluadas:**
  1. Conservar el LOO 1D por corte independiente.
  2. Realizar validación solo in-sample.
* **Motivo de la elección:** Atiende directamente al hallazgo H3 de Codex, proporcionando una métrica rigurosa y defendible fuera de muestra sobre la superficie 2D final utilizada por los consumidores del modelo.
* **Evidencia:** Tabla `outputs/tables/surface_final_holdout_validation.csv` y prueba `test_2d_final_holdout_validation_accuracy`.

---

## 2. Limitaciones Identificadas y Mitigaciones Metodológicas

1. **Diferencia entre Condiciones Europeas SVI y Coherencia Económica Americana:**
   * *Limitación:* Las condiciones clásicas de Gatheral & Jacquier ($g(k) \ge 0, \frac{\partial w}{\partial \tau} \ge 0$) son estrictamente válidas para superficies de volatilidad implícita europeas. En este proyecto, la superficie se ajusta sobre volatilidades implícitas recuperadas de opciones americanas mediante Crank-Nicolson.
   * *Mitigación:* Se reconoce formalmente esta distinción. La ausencia de arbitraje europeo en SVI garantiza la coherencia de la función generadora de volatilidades, pero la validez económica final de los precios de las opciones americanas se corrobora mediante pruebas dedicadas en el motor EDP: cotas intrínsecas ($C \ge (S-K)^+$, $P \ge (K-S)^+$), monotonía respecto al strike y monotonicidad en madurez ($V(\tau_2) \ge V(\tau_1)$).

2. **Alcance de las Validaciones Numéricas en Malla Finita:**
   * *Limitación:* Las comprobaciones numéricas de ausencia de arbitraje de calendario y mariposa se ejecutan sobre mallas discretas densas de log-moneyness ($k \in [-0.6, +0.6]$) y madureces. Ninguna prueba numérica sobre malla finita constituye una demostración analítica de ausencia de arbitraje en $\mathbb{R}^2$.
   * *Mitigación:* Se acotan con precisión el dominio de validez, la resolución de la discretización y las tolerancias numéricas ($10^{-6}$ a $10^{-4}$ USD). En regiones fuera del soporte empírico observado, se activan banderas explícitas de extrapolación (`EXTRAPOLATED_LOCAL_SLICE` o `EXTRAPOLATED_GLOBAL_DOMAIN`), prohibiendo cualquier pretensión de garantía matemática universal.

3. **Carácter Académico e Hipotético de las Estrategias de Trading:**
   * *Limitación:* El proyecto no cuenta con datos intradiarios de libro de órdenes con cotizaciones ejecutables en tiempo real ni con series continuas de contratos vencidos.
   * *Mitigación:* Se prohíbe categóricamente presentar los resultados como "rentabilidades históricas comprobadas" o "recomendaciones de inversión". Todas las estrategias son simulaciones analíticas prospectivas basadas en modelos de equilibrio y supuestos conservadores de fricción transaccional (spreads, comisiones y slippage).

4. **Anomalías Empíricas en Opciones LEAPS de Muy Largo Plazo (Vencimiento Enero 2029):**
   * *Limitación:* En el vencimiento de 794 días (2029-01-19), los contratos profundamente dentro del dinero (como la Call $K=3.0$ con última transacción a $\$10.25$ e IV implícita de $103.88\%$) exhiben distorsiones por extrema iliquidez y falta de cotizaciones actualizadas.
   * *Mitigación:* El corte se calibra mediante fallback PCHIP, se documenta la anomalía de convexidad ($89.47\%$ de convexidad en precios) y se restringe su estatus a `EMPIRICAL_ANOMALIES_DETECTED`. Para fines de pricing de alta precisión, se recomienda limitar el dominio de este corte al rango de strikes líquidos ($K \ge 5.0$).
