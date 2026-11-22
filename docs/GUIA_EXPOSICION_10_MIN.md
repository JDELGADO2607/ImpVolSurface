# Guía de Exposición Oral (10 Minutos) — Proyecto de Opciones Americanas de NU

**Público objetivo:** Comité de Riesgos, Mesa de Derivados y Dirección Cuantitativa de la entidad.  
**Tiempo total asignado:** 10 minutos (8 diapositivas de contenido, ~1:15 min por diapositiva).  
**Objetivo de la sesión:** Demostrar por qué el supuesto de volatilidad constante de Black-Scholes es inaceptable para la gestión de riesgos de NU Holdings (NYSE: NU) y presentar la arquitectura integral de valoración americana, superficie SVI, stress testing y estrategias cuantitativas.

---

## Estructura Temporal y Resumen Ejecutivo

| Diapositiva | Título del Bloque | Tiempo Asignado | Mensaje Clave |
|---|---|---|---|
| **1** | El Problema Financiero y el Caso Empresarial | 0:00 – 1:15 | Black-Scholes plano distorsiona precios y sensibilidades de NU. |
| **2** | Diagnóstico Forense y Auditoría de Datos | 1:15 – 2:30 | 575 contratos originales; filtrado riguroso a 201 opciones limpias. |
| **3** | Motor de Valoración Americano e Inversión Brent | 2:30 – 3:45 | BSM analítico en Calls ($q=0$) y Crank-Nicolson + Penalización en Puts. |
| **4** | Calibración de la Superficie de Volatilidad (SVI) | 3:45 – 5:00 | Parametrización Raw SVI libre de arbitraje ($g(k) \ge 0$) y validación OOS. |
| **5** | Comparación de los Cuatro Modelos de Pricing | 5:00 – 6:15 | Aislamiento del efecto sonrisa frente a la prima de ejercicio anticipado. |
| **6** | Portafolio Hipotético, Griegas y Stress Testing | 6:15 – 7:30 | La aproximación de Taylor falla en crisis; la revaloración PDE es mandatoria. |
| **7** | Estrategias Cuantitativas y Límites de Datos | 7:30 – 8:45 | Pronóstico HAR-RV (72.97%) vs IV ATM (44.02%) y Calendar Spread. |
| **8** | Recomendaciones Finales y Hoja de Ruta | 8:45 – 10:00 | Política de cuatro pilares para la mesa de derivados y control de riesgos. |

---

## Guion Detallado Diapositiva por Diapositiva

### Diapositiva 1: El Problema Financiero y el Caso Empresarial (0:00 – 1:15)
* **Contenido Visual:**
  * Diagrama de flujo del mandato institucional (Puntos 46 a 56).
  * Gráfico conceptual: Discrepancia entre la curva plana de Black-Scholes y los precios observados de mercado.
* **Guion del Expositor:**
  > "Buenos días, miembros del comité. Una mesa de derivados que utilice Black-Scholes clásico con una sola volatilidad constante para valorar y gestionar opciones sobre Nu Holdings comete dos errores estructurales: ignora la prima de ejercicio anticipado de las opciones americanas y desestima la sonrisa de volatilidad generada por el riesgo de cola y la asimetría del mercado. Nuestro objetivo es implementar una infraestructura cuantitativa rigurosa basada en diferencias finitas, calibrar una superficie de volatilidad implícita libre de arbitraje estático, someter una cartera fija a stress testing multifactorial y formular estrategias de volatilidad con supuestos de costos reales."

---

### Diapositiva 2: Diagnóstico Forense y Auditoría de Datos (1:15 – 2:30)
* **Contenido Visual:**
  * Tabla resumen de auditoría: 575 contratos brutos $\to$ 201 contratos limpios (16 vencimientos).
  * Visualización de anomalías detectadas: dispersión de `lastTradeDate` (291 transacciones el 17-nov-2026), reseteo de bid/ask a cero en 538 contratos y corrección de la madurez $\tau$ (3.0 días reales vs 1.0 día truncado en Excel).
* **Guion del Expositor:**
  > "Trabajamos sobre una cadena de 575 contratos reales de NU en 16 vencimientos. El examen forense reveló que ningún contrato negoció el 18 de noviembre: todas las operaciones líquidas ocurrieron el 17 de noviembre, cerrando a las 15:59:55 EST con $S_0 = 12.33$ USD. Por ende, fijar la fecha base en el cierre del 17 de noviembre es imperativo para evitar asincronías artificiales. Detectamos además que el 94% de las filas tenían bid y ask en cero por reseteo matutino de Yahoo, y que `yearsToExpiry` sufría corrupción por separador decimal y truncamiento a días enteros. Recalculamos $\tau$ bajo Act/365F continuo y clasificamos la base en cuatro Tiers: 201 contratos satisfacen estrictamente cotas de no arbitraje, valor tiempo positivo y condicionamiento $\kappa \le 5.0$ puntos de vol por centavo."

---

### Diapositiva 3: Motor de Valoración Americano e Inversión Brent (2:30 – 3:45)
* **Contenido Visual:**
  * Ecuación de Black-Scholes para Calls y formulación de Complementariedad Lineal (LCP) para Puts americanas.
  * Esquema numérico: Crank-Nicolson con suavizado de Rannacher y método de penalización (Forsyth & Vetzal, 2002).
  * Tabla de validación independiente: Discrepancia PDE vs árbol CRR ($N=1000$) menor a $\$0.0005$ USD ($< 0.05$ centavos).
* **Guion del Expositor:**
  > "Para la valoración diferenciamos la naturaleza económica de los contratos. Dado que NU no paga dividendos ($q=0$) y las tasas son positivas ($r > 0$), el teorema de Merton demuestra que el ejercicio anticipado de una Call americana nunca es óptimo; por ende, utilizamos la fórmula cerrada de Black-Scholes, exacta y computacionalmente instantánea. Para las Puts americanas, donde el cobro inmediato del strike puede ser óptimo, implementamos un esquema de diferencias finitas Crank-Nicolson con suavizado de Rannacher para amortiguar oscilaciones del payoff y el método de penalización cuadrático de Forsyth & Vetzal. Validamos el motor contra un árbol CRR de 1000 pasos, logrando una concordancia de medio milésimo de dólar. La inversión a volatilidad implícita se ejecuta mediante el algoritmo de Brent, garantizando convergencia sin riesgo de división por cero."

---

### Diapositiva 4: Calibración de la Superficie de Volatilidad (SVI) y Monotonicidad Temporal (3:45 – 5:00)
* **Contenido Visual:**
  * Figura 1: [smile_2d_slices.png](outputs/figures/smile_2d_slices.png) (Cortes de sonrisa 2D por vencimiento).
  * Figura 2: [surface_3d_volatility.png](outputs/figures/surface_3d_volatility.png) (Superficie 3D en coordenadas $(k, \tau)$).
  * Métricas de validación cruzada Leave-One-Strike-Out (197 contratos evaluados con EDP americana en puts): MAE Precio = $\$0.0389$ USD, RMSE Precio = $\$0.0649$ USD.
  * Verificación analítica y numérica de no arbitraje:
    * SVI Paramétrico: Condición de alas de Roger Lee ($b(1+|\rho|) \le 1.95 < 2.0$) y densidad mariposa ($g(k) \ge 0$) al 100% sobre el soporte empírico.
    * Fallback PCHIP: Validación económica explícita mediante diferencias divididas de convexidad de precios ($\frac{\Delta^2 C}{\Delta K^2} \ge 0$), erradicando garantías ficticias (reportando `NaN` en la fórmula SVI).
    * Consistencia temporal: Proyección monótona acumulativa unificada tanto en nodos exactos como en puntos interpolados, garantizando $\frac{\partial w}{\partial \tau} \ge 0$ y continuidad $C^1$ (resolución definitiva de los Casos A y B de auditoría).
* **Guion del Expositor:**
  > "Proyectamos la cadena en coordenadas estandarizadas de log-forward moneyness $k = \ln(K/F)$ y varianza total $w(k,\tau) = \sigma^2 \tau$. Calibramos la parametrización Raw SVI de Gatheral por cortes temporales, restringiendo estrictamente los parámetros a las cotas asintóticas de Roger Lee ($b(1+|\rho|) < 2.0$) y garantizando ausencia de arbitraje mariposa analítico ($g(k) \ge 0$) en el 100% del soporte en cortes SVI. Para los vencimientos con pocos strikes, activamos un fallback conservador en PCHIP, validado económicamente mediante diferencias divididas de convexidad sin atribuirle fórmulas analíticas que no le corresponden. Crucialmente, unificamos la evaluación temporal mediante proyección acumulativa monótona $w^*(\tau_i, k)$: la superficie garantiza ausencia de arbitraje de calendario tanto en los vencimientos originales como en los intermedios, sin saltos artificiales. Sometimos la superficie a validación cruzada Leave-One-Strike-Out con pricing PDE completo sobre 197 contratos: el MAE fuera de muestra fue de apenas 3.89 centavos de dólar, demostrando una generalización económica impecable sin sobreajuste."

---

### Diapositiva 5: Comparación de los Cuatro Modelos de Pricing (5:00 – 6:15)
* **Contenido Visual:**
  * Figura: [model_comparison_errors.png](outputs/figures/model_comparison_errors.png) (Comparación de MAE entre los 4 modelos por segmento).
  * Tabla comparativa dentro de muestra (In-Sample, $N=201$):
    * M1 (Europeo Plano): MAE = $\$0.0536$, RMSE = $\$0.0891$
    * M2 (Europeo Superficie): MAE = $\$0.0297$, RMSE = $\$0.0565$
    * M3 (Americano Plano): MAE = $\$0.0482$, RMSE = $\$0.0816$
    * M4 (Americano Superficie): MAE = $\$0.0285$, RMSE = $\$0.0480$
    * Validación Fuera de Muestra (LOO CV Americano): MAE = $\$0.0389$, RMSE = $\$0.0649$
* **Guion del Expositor:**
  > "Para cuantificar con rigor el impacto de cada supuesto, evaluamos la matriz $2 \times 2$ entre tipo de ejercicio (Europeo vs Americano) y estructura de volatilidad (Plana vs Superficie). En Calls, el Modelo 1 coincide con el Modelo 3, y el Modelo 2 con el Modelo 4, ratificando la teoría de Merton ($q=0$). En Puts, la prima de ejercicio anticipado es capturada con exactitud por las diferencias finitas. No obstante, el factor preponderante es la sonrisa de volatilidad: pasar de volatilidad plana a la superficie SVI reduce el error medio en un 40.9% general y en un 48.4% en contratos ITM, recortando el MAE de $\$0.0854$ a $\$0.0398$. Black-Scholes plano subvalora sistemáticamente las alas OTM y genera sesgos inaceptables para la gestión de coberturas."

---

### Diapositiva 6: Portafolio Hipotético, Griegas y Stress Testing (6:15 – 7:30)
* **Contenido Visual:**
  * Estructura de cartera: 5 patas de opciones reales en 31 y 59 días + cobertura delta con -357 acciones de NU ($\Delta_{\text{neto}} = +0.11$).
  * Figura 1: [stress_test_pnl_waterfall.png](outputs/figures/stress_test_pnl_waterfall.png) (P&L por escenario: Revaloración PDE vs Taylor).
  * Figura 2: [stress_crisis_leg_breakdown.png](outputs/figures/stress_crisis_leg_breakdown.png) (Desglose por pata en el Escenario 3 de Crisis Severa).
  * Métricas clave: Escenario Nulo validado ($\text{P\&L} \equiv \$0.00$), Diferencia inicial Mark-to-Model aislada ($-\$20.43$ USD), Capital Económico de Margen ($\$5,435.31$ USD).
* **Guion del Expositor:**
  > "Construimos una cartera de 5 patas representativa de una mesa institucional: spreads verticales, straddles y calendars, neutralizada en delta inicial mediante una posición corta de 357 acciones de NU. Estabilizamos las griegas numéricas fijando el dominio espacial $S_{\max}$ e interpolando con PCHIP, resolviendo el defecto que inflaba el Gamma de la Put $K=12$ a 3.35 y corrigiéndolo a 0.2375. Al someter la cartera a cinco escenarios de estrés con contabilidad dual (aislando el error de marca inicial de $-\$20.43$ USD), comprobamos que en el Escenario Nulo el P&L es exactamente cero. En el Escenario 3 de Crisis Severa (-20% en spot, +12 pp vol y empinamiento de skew), la revaloración PDE completa arroja un beneficio real de $+\$496.56$ USD frente a $+\$757.71$ USD estimados por Taylor, revelando una discrepancia genuina de $-\$261.15$ USD. La literatura previa reportaba $-\$3,253$ USD, cifra que desmitificamos: estaba inflada por el Gamma numérico inestable. La revaloración completa por EDP es insustituible para capturar la asimetría del colapso de las Calls y el ejercicio anticipado de Puts."

---

### Diapositiva 7: Estrategias Cuantitativas y Límites de Datos (7:30 – 8:45)
* **Contenido Visual:**
  * Figura 1: [nu_historical_vol_and_forecasts.png](outputs/figures/nu_historical_vol_and_forecasts.png) (Serie histórica y pronóstico HAR-RV purificado).
  * Figura 2: [strategy1_payoff_scenarios.png](outputs/figures/strategy1_payoff_scenarios.png) (Curvas de P&L de la Estrategia 1 bajo tres regímenes de fricción y conexión estricta de señal).
  * Figura 3: [strategy2_calendar_payoff.png](outputs/figures/strategy2_calendar_payoff.png) (Payoff del Calendar Spread a strike fijo $K=13.00$).
* **Guion del Expositor:**
  > "Desarrollamos dos estrategias cuantitativas defendibles sin sesgo de anticipación. En la Estrategia 1, calibramos el modelo heterogéneo HAR-RV mediante validación walk-forward estrictamente purificada ($s \le t-21$), eliminando cualquier fuga del objetivo a 21 días (QLIKE = 0.1855, superior a EWMA 0.2099 y rolling 0.2512). Al 17 de noviembre, el pronóstico causal fue de 72.97% frente a una IV combinada de 45.90%, superando el umbral de 5 pp y activando la señal `LONG_VOLATILITY_STRADDLE`. Separamos rigurosamente la señal de la ejecución simulada: la estructura abrió $+1$ Call, $+1$ Put y una cobertura delta exacta de $-23$ acciones de NU (utilizando el delta americano de la put de -0.3839). Si el pronóstico se ubicara en la banda neutral, la simulación arroja estrictamente cero contratos, cero costos y cero P&L. En la Estrategia 2, extrajimos la volatilidad forward a strike fijo $K=13.00$ entre 31 y 59 días ($\sigma_{\text{fwd}} = 38.15\%$) mediante un Calendar Spread. Modelamos tres regímenes de costos y enfatizamos que son simulaciones académicas prospectivas, no órdenes de ejecución ni promesas de rentabilidad histórica."

---

### Diapositiva 8: Recomendaciones Finales y Hoja de Ruta (8:45 – 10:00)
* **Contenido Visual:**
  * Matriz ejecutiva de gobernanza: Cuatro pilares de adopción cuantitativa para la entidad.
  * Hoja de ruta técnica de despliegue a producción.
* **Guion del Expositor:**
  > "En conclusión, respondemos a la pregunta ejecutiva de la entidad con cuatro recomendaciones innegociables:
  > 1. **Eliminar Black-Scholes con volatilidad plana** de la tarificación y de las métricas de capital regulatorio; induce sesgos de hasta el 54% en ITM y distorsiona la cobertura delta.
  > 2. **Adoptar la superficie SVI calibrada diariamente** como la fuente oficial de marcado a modelo (*mark-to-model*), garantizando ausencia de arbitraje estático.
  > 3. **Instituir la revaloración completa americana por diferencias finitas en las pruebas de estrés periódicas**, reservando las griegas únicamente para monitoreo intradía de movimientos menores a 1 desvío estándar.
  > 4. **Acondicionar las estrategias algorítmicas a filtros de iliquidez estrictos** ($\kappa \le 3.0$ pp/¢) y descontar rigurosamente el costo de bid-ask bounce y márgenes de garantía.
  > Muchas gracias. Quedamos a su disposición para la sesión de preguntas."
