# Catálogo Exhaustivo de Preguntas de Defensa (25+ Preguntas Clave)

Este documento recopila las 28 preguntas técnicas, metodológicas, financieras y computacionales más exigentes que el tribunal evaluador, el comité de riesgos o la mesa de derivados pueden formular durante la defensa del proyecto, acompañadas de sus respuestas cuantitativas fundamentadas, demostraciones matemáticas y evidencia empírica directa.

---

## Bloque 1: Integridad de Datos, Fecha Base y Tratamiento Forense

### Pregunta 1: ¿Por qué fijaron la fecha de valoración en el 17 de noviembre de 2026 a las 16:00 EST si el archivo se descargó el 18 de noviembre por la mañana?
* **Respuesta fundamentada:**
  El examen forense de los 575 contratos demostró que **ninguna transacción ocurrió el 18 de noviembre**. Los 291 contratos más líquidos transaron exclusivamente durante la sesión del 17 de noviembre, culminando exactamente a las 15:59:55 EST (cierre regular del mercado). Si hubiéramos asignado el 18 de noviembre como fecha base, habríamos valorado contratos cuyos precios reflejaban el estado de mercado del 17-nov ($S_0 = 12.33$ USD) utilizando una madurez $\tau$ reducida artificialmente en casi un día entero. En el primer vencimiento (20 de noviembre), donde restaban exactamente 3 días calendario desde el cierre del 17-nov, descontar un día artificial habría subestimado $\tau$ en un 33%, duplicando espuriamente la volatilidad implícita calculada de 45% a más del 90%. Por el principio de causalidad y coherencia macroeconómica, el estado de mercado base debe anclarse estrictamente al instante en que se formaron los precios observables ($S_0 = 12.33$ USD al cierre del 17-nov).

### Pregunta 2: ¿Por qué descartaron el filtro estándar `bid > 0`? ¿No es peligroso usar `lastPrice` en contratos ilíquidos?
* **Respuesta fundamentada:**
  En el archivo original, 538 de los 575 contratos (93.57%) presentaban `bid = 0` y `ask = 0`. Esto se debe a que Yahoo Finance resetea las cotizaciones bilaterales tras el cierre del mercado y previo a la apertura. Los únicos 32 contratos con `bid > 0` contenían cotizaciones obsoletas de hace varios meses (febrero a octubre de 2026), muchas de las cuales violaban flagrantemente el valor intrínseco. Exigir `bid > 0` habría destruido la muestra líquida y dejado únicamente registros corruptos. Para mitigar el riesgo de utilizar `lastPrice`, no aceptamos los precios ciegamente: aplicamos un filtro de condicionamiento numérico riguroso $\kappa = 0.01 / \text{Vega} \le 3.0$ pp/centavo y exigimos valor tiempo $TV \ge 0.01$ USD y precio mínimo $\ge 0.05$ USD. Esto aisló 201 contratos de alta calidad (Tier 1 + 2) donde el error de cuantización de un centavo tiene un impacto acotado y controlable.

### Pregunta 3: ¿A qué se debía la presencia de números del orden de $10^{16}$ en `yearsToExpiry` y volatilidades de $10^{11}$ en Yahoo Finance?
* **Respuesta fundamentada:**
  Fueron dos patologías independientes:
  1. **`yearsToExpiry`:** Se debió a un conflicto de localización regional en Excel. Al abrir un archivo configurado con coma decimal en un sistema con punto decimal (o viceversa), los valores numéricos superiores o iguales a 1.0 fueron interpretados como miles repetidos, desplazando el separador decimal 16 posiciones (por ejemplo, $1.0027378\dots$ se transformó en $1.0027378 \times 10^{16}$). Además, en los contratos menores a un año, la fórmula original truncaba a enteros hasta medianoche, perdiendo la precisión intradiaria. Se corrigió recalculando $\tau$ bajo Act/365F continuo con marca horaria de 16:00 EST.
  2. **`impliedVolatility` de Yahoo:** Yahoo Finance utiliza un algoritmo de bisección numérico. Cuando el bid y el ask son cero, el motor intenta invertir un precio objetivo nulo o cercano al piso numérico $10^{-5}$, quedando atrapado en fracciones diádicas exactas ($0.500005, 0.2500075$) o escalando el piso a $10^{11}$ por el mismo error de localización. Por ello, la volatilidad de Yahoo fue descartada por completo de la calibración.

---

## Bloque 2: Supuestos Financieros, Ausencia de Dividendos y Ejercicio Anticipado

### Pregunta 4: ¿Por qué asumen dividendos nulos ($q = 0$)? ¿Qué ocurriría si NU comenzara a pagar dividendos?
* **Respuesta fundamentada:**
  Nu Holdings Ltd. no ha pagado dividendos ordinarios ni extraordinarios en toda su historia bursátil (dividendo TTM = 0.00 USD), hecho ratificado en el Formulario 6-K radicado ante la SEC el 12 de noviembre de 2026. Si NU decretara dividendos continuos $q > 0$ (o dividendos discretos), el costo de oportunidad de no ejercer una Call americana antes de la fecha ex-dividendo podría superar el valor temporal residual. En ese escenario, $C_{\text{American}} > C_{\text{European}}$ en contratos ITM y la Call admitiría ejercicio anticipado, obligando a resolver la EDP con frontera libre también para las Calls. Bajo $q = 0$ y $r \ge 0$, el ejercicio anticipado de la Call nunca es óptimo.

### Pregunta 5: Demuestre formalmente por qué para una Call americana sobre un activo sin dividendos ($q=0$) y tasas no negativas ($r \ge 0$) el ejercicio anticipado nunca es óptimo.
* **Respuesta fundamentada:**
  Sea $C_{\text{Am}}(S, t)$ el valor de la Call americana y $C_{\text{Eu}}(S, t)$ el valor de la Call europea con mismo strike $K$ y vencimiento $T$.
  Por definición de opcionalidad, $C_{\text{Am}}(S, t) \ge C_{\text{Eu}}(S, t)$.
  Bajo ausencia de arbitraje, la cota inferior estricta de una Call europea sin dividendos es:
  $$C_{\text{Eu}}(S, t) \ge S_t - K e^{-r(T-t)}$$
  Dado que $r \ge 0$ y $\tau = T - t \ge 0$, se cumple que $e^{-r\tau} \le 1$, lo que implica:
  $$S_t - K e^{-r\tau} \ge S_t - K$$
  Por tanto, para todo $\tau > 0$:
  $$C_{\text{Am}}(S, t) \ge C_{\text{Eu}}(S, t) \ge S_t - K e^{-r\tau} > S_t - K$$
  Si el titular ejerciera anticipadamente en $t < T$, recibiría únicamente el payoff intrínseco $S_t - K$. Dado que el valor de continuación en mercado $C_{\text{Am}}(S, t)$ es estrictamente mayor que $S_t - K$, vender la opción en el mercado o mantenerla siempre domina al ejercicio anticipado. Por ende, el ejercicio anticipado nunca es óptimo y $C_{\text{Am}}(S, K, \tau) \equiv C_{\text{Eu}}(S, K, \tau)$.

### Pregunta 6: ¿Por qué sí puede ser óptimo ejercer anticipadamente una Put americana bajo las mismas condiciones ($q=0, r > 0$)?
* **Respuesta fundamentada:**
  Para una Put, el payoff de ejercicio es $K - S_t$. Si el subyacente cae fuertemente hacia cero ($S_t \to 0$), el valor del ejercicio es cercano a $K$. Al ejercer anticipadamente, el titular recibe el capital en efectivo $K$ de inmediato y puede invertirlo a la tasa libre de riesgo $r > 0$, devengando intereses de forma continua. Por el contrario, si mantiene la opción hasta el vencimiento $T$, el valor máximo que puede recibir en $T$ sigue acotado por $K$, cuyo valor presente descontado es solo $K e^{-r\tau} < K$. La pérdida de valor tiempo por el descuento de los fondos recibidos supera cualquier beneficio especulativo de caídas adicionales del subyacente, haciendo óptimo el ejercicio anticipado por debajo de una frontera crítica de precio $S^*(\tau) < K$.

---

## Bloque 3: Métodos Numéricos de Ecuaciones Diferenciales Parciales

### Pregunta 7: ¿Cómo nace la aproximación de diferencias finitas y por qué el error de Crank-Nicolson es de segundo orden $O(\Delta t^2 + \Delta S^2)$?
* **Respuesta fundamentada:**
  Nace del desarrollo en serie de Taylor alrededor del nodo de malla:
  $$V(S + \Delta S) = V(S) + \frac{\partial V}{\partial S} \Delta S + \frac{1}{2} \frac{\partial^2 V}{\partial S^2} \Delta S^2 + \frac{1}{6} \frac{\partial^3 V}{\partial S^3} \Delta S^3 + O(\Delta S^4)$$
  $$V(S - \Delta S) = V(S) - \frac{\partial V}{\partial S} \Delta S + \frac{1}{2} \frac{\partial^2 V}{\partial S^2} \Delta S^2 - \frac{1}{6} \frac{\partial^3 V}{\partial S^3} \Delta S^3 + O(\Delta S^4)$$
  Al restar ambas ecuaciones, los términos pares se cancelan, dejando una aproximación central de primer orden con error $O(\Delta S^2)$:
  $$\frac{\partial V}{\partial S} = \frac{V(S + \Delta S) - V(S - \Delta S)}{2 \Delta S} + O(\Delta S^2)$$
  Al sumar ambas ecuaciones, los términos impares se cancelan, obteniendo la segunda derivada con error $O(\Delta S^2)$:
  $$\frac{\partial^2 V}{\partial S^2} = \frac{V(S + \Delta S) - 2V(S) + V(S - \Delta S)}{\Delta S^2} + O(\Delta S^2)$$
  En el tiempo, Crank-Nicolson evalúa el operador espacial en el punto medio temporal $\tau + \frac{\Delta \tau}{2}$ promediando el paso explícito ($\theta = 0.5$) y el implícito. La expansión de Taylor en $\tau$ cancela el término lineal del error de truncamiento temporal, elevando la precisión a segundo orden $O(\Delta \tau^2)$.

### Pregunta 8: ¿Por qué Crank-Nicolson puro puede oscilar numéricamente en opciones y por qué es indispensable el suavizado de Rannacher?
* **Respuesta fundamentada:**
  Crank-Nicolson es $A$-estable, pero **no es $L$-estable**. Su factor de amplificación para modos de Fourier de muy alta frecuencia $\lambda \to \infty$ tiende a $-1$ en lugar de amortiguarse a cero. El payoff inicial de una opción en $\tau = 0$ presenta una discontinuidad en su primera derivada en el strike $S = K$ (singularidad de Dirac en Gamma). Esta discontinuidad excita modos de alta frecuencia que Crank-Nicolson preserva con signo alternado, generando oscilaciones espurias de dientes de sierra en las griegas y en el precio.
  El suavizado de Rannacher (1984) soluciona esto reemplazando los primeros pasos temporales con sub-pasos implícitos puros ($\theta = 1.0$), los cuales son $L$-estables y poseen un factor de amplificación que tiende a cero cuando la frecuencia espacial crece, amortiguando instantáneamente la rugosidad del payoff inicial sin degradar la precisión global de segundo orden.

### Pregunta 9: ¿Cómo funciona el método de penalización cuadrática de Forsyth & Vetzal (2002) frente a PSOR?
* **Respuesta fundamentada:**
  El método de penalización reformula el problema de complementariedad lineal (LCP) americano:
  $$\frac{\partial V}{\partial \tau} - \mathcal{L} V - \rho \max(V^* - V, 0) = 0$$
  donde $V^*$ es el payoff intrínseco y $\rho \gg 1$ es un parámetro de penalización grande ($10^7$).
  Discretizado en tiempo, se resuelve mediante una iteración de política de tipo Newton semisuave: en cada sub-iteración $k$, se define la matriz diagonal de penalización $P_{jj}^{(k)} = \rho$ si $V_j^{(k)} < V_j^*$, y $0$ en caso contrario. Se resuelve el sistema tridiagonal lineal $(I - \Delta \tau \theta \mathcal{L} + P^{(k)}) V^{(k+1)} = b^{(k)}$.
  A diferencia de PSOR (Projected Successive Over-Relaxation), que es un solver iterativo punto a punto dependiente de un parámetro de relajación $\omega \in (1, 2)$ sensible y que requiere cientos de iteraciones cerca de vencimiento, el método de penalización utiliza inversión tridiagonal directa (Algoritmo de Thomas) y converge cuadráticamente en solo 2 a 3 iteraciones por paso temporal, con independencia incondicional de la malla.

### Pregunta 10: ¿Cómo validaron independientemente que el motor de diferencias finitas no contenía errores de codificación?
* **Respuesta fundamentada:**
  Ejecutamos tres pruebas de validación cruzada independiente:
  1. Para Calls con $q=0$, contrastamos el motor de diferencias finitas contra la fórmula analítica exacta de Black-Scholes: la discrepancia máxima fue de $\$0.00048$ USD ($< 0.05$ centavos).
  2. Para Puts americanas, contrastamos el motor EDP contra un árbol binomial Cox-Ross-Rubinstein (CRR) de 1000 pasos en múltiples plazos y moneyness: la diferencia se mantuvo por debajo de $\$0.00050$ USD.
  3. Ejecutamos pruebas de refinamiento de malla duplicando nodos espaciales ($M = 150 \to 300 \to 600$) y temporales ($N = 75 \to 150 \to 300$), confirmando convergencia numérica monótona sin oscilaciones espurias.

### Pregunta 10b: ¿A qué se debía la inestabilidad de Gamma en la Put K=12 (3.3547 vs 0.2375) y cómo se corrigió matemáticamente?
* **Respuesta fundamentada:**
  Al calcular segundas derivadas por diferencias centrales:
  $$\Gamma = \frac{V(S_0 + dS) - 2V(S_0) + V(S_0 - dS)}{dS^2}$$
  El código original definía la cota superior del dominio espacial como $S_{\max}(S) = 4.0 \cdot \max(S, K)$. Al evaluar con perturbación $dS = 0.01$, el dominio $[0, S_{\max}]$ cambiaba ligeramente en las tres evaluaciones, construyendo **tres mallas discretas desalineadas**. La interpolación cúbica subsiguiente introducía un error de discretización del orden de $O(\Delta S^2)$; al dividirse por el denominador cuadrático $dS^2 = (0.01)^2 = 10^{-4}$, este ruido numérico se multiplicaba por $10\,000\times$, arrojando un Gamma artificial de $3.3547$ para la Put $K=12$.
  
  La corrección matemática consistió en:
  1. Fijar un dominio espacial común e invariante $S_{\max} = 4.0 \cdot \max(S_0, K)$ compartido por todas las perturbaciones.
  2. Resolver la EDP una sola vez sobre dicha malla compartida (\texttt{fd\_american\_grid}) y evaluar los puntos perturbados sobre la solución continua unificada mediante interpolación PCHIP local monótona, suprimiendo sobreoscilaciones espurias.
  3. Tras la corrección, el Gamma de la Put $K=12$ convergió suavemente a **$0.2375$**, en perfecta consistencia con el Gamma europeo ($0.2346$) más la curvatura adicional propia de la prima de ejercicio anticipado.

---

## Bloque 4: Inversión de Volatilidad Implícita y Contraste con Bloomberg

### Pregunta 11: ¿Por qué eligieron el algoritmo de Brent en lugar de Newton-Raphson para la inversión de volatilidad?
* **Respuesta fundamentada:**
  Newton-Raphson actualiza la volatilidad como $\sigma_{n+1} = \sigma_n - \frac{V(\sigma_n) - P_{\text{mkt}}}{\nu(\sigma_n)}$, donde $\nu$ es la Vega de la opción. En contratos profundamente fuera del dinero (OTM) o dentro del dinero (ITM), la Vega tiende exponencialmente a cero ($\nu \to 0$). Cualquier perturbación numérica o precio con ruido hace que el denominador colapse, provocando pasos descontrolados hacia volatilidades negativas o infinitas y divergencia fatal.
  El algoritmo de Brent combina interpolación cuadrática inversa y el método de la secante para una convergencia superlineal rápida, pero conmuta automáticamente a bisección garantizada si la extrapolación escapa del intervalo de búsqueda acotado $[0.01, 5.00]$. Esto garantiza un 100% de éxito en la convergencia siempre que el precio satisfaga las cotas de no arbitraje.

### Pregunta 12: ¿Por qué un residuo de inversión pequeño no garantiza que la volatilidad implícita sea económicamente informativa?
* **Respuesta fundamentada:**
  Por la relación de condicionamiento local $\Delta \sigma \approx \frac{\Delta P}{\text{Vega}}$.
  En contratos con Vega microscópica (por ejemplo, una opción OTM con madurez corta donde $\text{Vega} = 0.002$ USD por punto de vol), el solver puede encontrar una volatilidad $\sigma$ cuyo precio del modelo difiere del precio objetivo en apenas $\$0.0001$ USD (residuo numérico ínfimo). Sin embargo, en el mercado real, las opciones cotizan en ticks discretos de $\$0.01$ o $\$0.05$ USD. Un error de cotización o un rebote bid-ask de un solo centavo ($\Delta P = 0.01$) induciría una incertidumbre económica en la volatilidad de $\Delta \sigma = \frac{0.01}{0.002} = 5.0$ puntos porcentuales. Un residuo de optimización pequeño solo demuestra convergencia matemática del algoritmo, no significancia estadística ni estabilidad financiera del dato.

### Pregunta 13: Si nuestras IVs calculadas difieren de Bloomberg en el primer vencimiento (20-nov) en 8 a 12 pp, ¿significa que nuestro modelo está errado?
* **Respuesta fundamentada:**
  No. Dicha diferencia es un hallazgo legítimo originado por la **asincronía temporal de ~21 horas** y el cambio de régimen de mercado:
  1. Las transacciones de Yahoo ocurrieron el 17 de noviembre antes de las 16:00 EST con el spot de NU en $12.33 USD.
  2. La captura de Bloomberg se realizó el 18 de noviembre a las 12:52 COT (~12:52 EST), cuando NU caía intradía hacia $12.08 USD (-2.03%).
  3. En un vencimiento a 3 días (20-nov), el transcurso de casi un día completo representa el consumo del 30% al 40% de la vida total del contrato.
  4. Además, Bloomberg evalúa cotizaciones Mid en vivo sobre precios cotizados al 18-nov, mientras nuestro motor invierte el `lastPrice` transado el 17-nov.
  En los vencimientos líquidos de 1 a 12 meses (donde el paso de 21 horas es marginal), nuestras IVs americanas replican a Bloomberg con diferencias mínimas de 0.1 a 1.5 pp. Modificar nuestras IVs para forzarlas a coincidir con Bloomberg violaría la independencia del cálculo e introduciría contaminación circular.

---

## Bloque 5: Superficie de Volatilidad, Modelo SVI y Validación

### Pregunta 14: ¿Qué ventajas ofrece la parametrización Raw SVI frente a un spline cúbico libre y qué cotas asintóticas se imponen?
* **Respuesta fundamentada:**
  Un spline cúbico sin restricciones tiende a generar oscilaciones locales espurias (*Runge phenomenon*) y sobreajuste en los extremos de la muestra, violando con frecuencia las condiciones de no arbitraje mariposa ($g(k) < 0$) y produciendo densidades de probabilidad neutral al riesgo negativas.
  Raw SVI modela la varianza total como una hipérbola asimétrica en log-moneyness $k$:
  $$w(k) = a + b \left[ \rho(k - m) + \sqrt{(k - m)^2 + \eta^2} \right]$$
  Esta estructura es lineal en las alas ($k \to \pm \infty$), lo que garantiza consistencia con la fórmula de momentos de Roger Lee:
  $$b(1 + |\rho|) < 2.0$$
  evitando colas excesivamente pesadas que invalidarían la existencia de momentos del subyacente ($\mathbb{E}[S_T] < \infty$). En nuestra calibración robusta, se impone $b(1+|\rho|) \le 1.95$. Si un corte temporal dispone de menos de 6 strikes o no alcanza convergencia libre de arbitraje, el motor conmuta automáticamente a un Fallback por Spline PCHIP monótono conservador.

### Pregunta 15: ¿Cómo verifican matemáticamente que la superficie calibrada no admite arbitraje estático europeo ni de calendario?
* **Respuesta fundamentada:**
  Verificamos dos condiciones analíticas rigurosas:
  1. **Ausencia de arbitraje mariposa (Densidad no negativa):** La función de densidad neutral al riesgo de Durrleman/Gatheral $g(k)$ debe ser no negativa para todo $k$:
     $$g(k) = \left( 1 - \frac{k w'(k)}{2 w(k)} \right)^2 - \frac{w'(k)^2}{4} \left( \frac{1}{w(k)} + \frac{1}{4} \right) + \frac{w''(k)}{2} \ge 0$$
     En nuestra superficie reparada, $g(k) \ge 0$ se verifica al **100.0%** sobre la malla de soporte empírico en todos los cortes temporales.
  2. **Ausencia de arbitraje de calendario:** La varianza total $w(k, \tau)$ debe ser estrictamente no decreciente en madurez: $\frac{\partial w(k, \tau)}{\partial \tau} \ge 0$. Para garantizar esto a través de todos los niveles de moneyness, se aplica una regularización acumulativa previa ($\widetilde{w}(k, \tau_j) = \max_{\tau' \le \tau_j} w(k, \tau')$) e interpolación temporal por PCHIP, garantizando cero violaciones de calendario en todo el dominio bidimensional.

### Pregunta 16: ¿Por qué la validación in-sample no es suficiente y qué arrojó la validación Leave-One-Strike-Out con pricing americano?
* **Respuesta fundamentada:**
  Calibrar por contrato de forma in-sample conduce mecánicamente a errores pequeños porque los parámetros absorben el ruido de microestructura de los precios observados.
  Para probar el verdadero poder predictivo del modelo, ejecutamos una validación cruzada Leave-One-Strike-Out agrupada sobre 197 contratos: retiramos secuencialmente cada strike de la muestra, re-calibramos la superficie sobre los strikes restantes y revaloramos el contrato excluido utilizando su motor exacto (Black-Scholes analítico para Calls y Crank-Nicolson con penalización para Puts americanas).
  El modelo obtuvo un error medio absoluto fuera de muestra de **MAE = $0.0389 USD** (apenas 3.89 centavos de dólar) y **RMSE = $0.0649 USD**, confirmando una capacidad de generalización económica superior sin sobreajuste.

---

## Bloque 6: Comparación de Modelos y Griegas

### Pregunta 17: ¿Cuáles fueron las conclusiones de la comparación entre los cuatro modelos (Europeo/Americano $\times$ Plano/Superficie)?
* **Respuesta fundamentada:**
  1. **Efecto de Ejercicio Anticipado:** En Calls, el Modelo 1 coincide exactamente con el Modelo 3 (MAE $0.0551), y el Modelo 2 con el Modelo 4 (MAE $0.0259), confirmando la teoría de Merton ($q=0$). En Puts, la prima americana reduce el MAE de $\$0.0515$ (M1) a $\$0.0386$ (M3) en plano, y de $\$0.0351$ (M2) a $\$0.0322$ (M4) en superficie.
  2. **Efecto de la Superficie de Volatilidad:** La incorporación de la superficie reduce el error de tarificación de manera sustancial:
     * En toda la muestra ($N=201$): el MAE dentro de muestra cae de $\$0.0536$ (M1) a **$\$0.0285$ USD (M4)** (reducción del 40.9%).
     * En opciones ITM ($N=72$): el MAE se reduce a casi la mitad, cayendo de $\$0.0854$ a **$\$0.0398$ USD** (reducción del 48.4%).
  3. **Conclusión Institucional:** El error de utilizar una volatilidad plana es de 3 a 5 veces mayor que el error de ignorar el ejercicio anticipado en contratos ATM/OTM. Por tanto, tarificar con volatilidad plana distorsiona severamente la gestión de riesgos de la entidad.

### Pregunta 18: ¿Cuáles son las unidades exactas de las Griegas calculadas y por qué Vega se escala a 1 punto porcentual?
* **Respuesta fundamentada:**
  * **Delta ($\Delta$):** Acciones equivalentes por opción ($\partial V / \partial S$).
  * **Gamma ($\Gamma$):** Variación de delta por cada dólar de cambio en el subyacente ($\partial^2 V / \partial S^2$), expresada en acciones/\$.
  * **Vega ($\nu$):** Variación del precio de la opción en dólares por **1 punto porcentual (0.01)** de cambio en la volatilidad ($\frac{\partial V}{\partial \sigma} \times 0.01$). Escalarla a 1 pp es el estándar de las mesas de trading, ya que un cambio de 1.0 en $\sigma$ representaría una duplicación del 100% de la volatilidad, un escenario no infinitesimal.
  * **Theta diaria ($\Theta_{\text{daily}}$):** Decaimiento temporal en dólares por cada día calendario transcurrido ($\frac{\Theta_{\text{annual}}}{365}$).
  * **Vanna:** Sensibilidad cruzada $\frac{\partial \Delta}{\partial \sigma} \times 0.01$, expresada en cambio de delta por 1 pp de vol.
  * **Volga:** Curvatura $\frac{\partial^2 V}{\partial \sigma^2} \times 0.0001$, en dólares por $(1\text{ pp})^2$.

---

## Bloque 7: Portafolio y Stress Testing de Cadena Fija

### Pregunta 19: ¿Por qué en el stress testing mantuvieron fija la cadena contractual y qué variables se actualizaron?
* **Respuesta fundamentada:**
  En una cartera institucional real, los contratos en custodia no mutan sus términos: el símbolo, el strike $K$ y la fecha de vencimiento $T$ permanecen inmutables.
  Ante el avance del tiempo $\Delta t$ o un shock de spot $\Delta S$, lo que cambia de forma endógena es:
  1. La madurez residual: $\tau_1 = \max(T - (t_0 + \Delta t), 0)$.
  2. El precio forward: $F_1 = S_1 \exp(r \tau_1)$.
  3. El moneyness: $k_1 = \ln(K / F_1)$.
  Esto actualiza la posición del contrato sobre la superficie de volatilidad implícita antes de ejecutar la revaloración completa con el motor de diferencias finitas.

### Pregunta 20: ¿Por qué la literatura previa del proyecto reportaba una discrepancia de Taylor de -$3,253 USD y cuál es la cifra real corregida?
* **Respuesta fundamentada:**
  La discrepancia de $-\$3\,253.04$ USD reportada anteriormente en el Escenario 3 (Crisis Severa, $\Delta S = -20\%$, $+12$ pp vol) no se debía exclusivamente a no-linealidad financiera, sino a dos defectos técnicos corregidos en la auditoría cuantitativa:
  1. **Inestabilidad de Gamma Numérico:** La Put $K=12$ ($\tau=31$ días) arrojaba un Gamma artificialmente inflado de $3.3547$ (en lugar del valor real de $0.2375$), originado por la desalineación de mallas al perturbar el spot con $S_{\max}(S)$ dinámico. Este error en Gamma, multiplicado por $\frac{1}{2} M q (\Delta S)^2$, inflaba el P&L de Taylor en $+\$2\,844$ USD espurios.
  2. **Contaminación por Marca a Modelo:** Se restaba el precio de mercado inicial en vez del precio de modelo inicial, sumando la discrepancia inicial de $-\$20.43$ USD.

  Al estabilizar el motor PDE (fijando $S_{\max}$ y usando interpolación PCHIP) y unificar la base contable del modelo:
  * El **P&L real de la EDP Completa** es de **$+\$496.56$ USD**.
  * El **P&L estimado por Taylor** es de **$+\$757.71$ USD**.
  * La **discrepancia de Taylor genuina** es de **$-\$261.15$ USD** (un 34.5% del P&L estimado).
  
  Esta discrepancia real sí representa fenómenos financieros genuinos: ante caídas de spot del 20%, las Calls largas colapsan asintóticamente a cero perdiendo su convexidad (mientras Taylor asume crecimiento cuadrático infinito), y las Puts cortas sufren aceleración de ejercicio anticipado.

### Pregunta 20b: ¿Cómo se verificó que la contabilidad de stress testing está perfectamente libre de desajustes iniciales?
* **Respuesta fundamentada:**
  Se introdujo el **Escenario Nulo (S0)** con perturbaciones idénticamente nulas ($\Delta S = 0$, $\Delta t = 0$, $\Delta \sigma = 0$, $\Delta r = 0$). En este escenario, tanto la revaloración completa por EDP como la expansión de Taylor arrojan **exactamente $0.00$ USD** de P&L. Asimismo, se separó la discrepancia inicial de marca a modelo ($\Pi_{0,\text{model}} - \Pi_{0,\text{market}} = -\$20.43$ USD), y se verificó que la sumatoria individual de P&L de las 5 patas de opciones más la cobertura de acciones ($-357$ acciones de NU) coincide al céntimo con el P&L total del portafolio.

### Pregunta 20c: ¿Por qué es un error metodológico presentar el valor absoluto de una cartera con posiciones cortas como "capital invertido"?
* **Respuesta fundamentada:**
  En una cartera con opciones vendidas y acciones cortas, el valor neto de mercado puede ser pequeño o negativo mientras el pasivo contingente es enorme. Sumar el valor absoluto de posiciones cortas no refleja fondos propios comprometidos, sino que distorsiona la métrica de rentabilidad. Implementamos el estándar regulatorio de margen (Reg T / FINRA 4210):
  $$C_{\text{margin}} = \text{Margen Acciones Cortas (50\%)} + \text{Margen Opciones Cortas} + \text{Costo Opciones Largas} = \$5\,435.31 \text{ USD}$$
  Sobre este capital económico de garantía, el P&L de $+\$496.56$ USD en el Escenario 3 representa un retorno prudencial del **$+9.14\%$**.

### Pregunta 21: ¿Qué diferencia existe entre la convención Sticky-Strike y Sticky-Moneyness?
* **Respuesta fundamentada:**
  * **Sticky-Strike (Regla del Strike Fijo):** Supone que la volatilidad implícita de una opción vinculada a un strike absoluto $K$ permanece constante cuando el spot $S$ se mueve: $\sigma(K, S_1) = \sigma(K, S_0)$.
  * **Sticky-Moneyness / Sticky-Delta (Regla del Moneyness Fijo):** Supone que la curva de sonrisa se traslada con el precio del activo, manteniendo constante la volatilidad para un nivel relativo de moneyness $k = \ln(K/F)$: $\sigma(k, S_1) = \sigma(k, S_0)$.
  En nuestro stress testing evaluamos ambas convenciones: bajo caídas severas del spot, Sticky-Moneyness refleja con mayor fidelidad el comportamiento empírico del mercado de renta variable, donde el sesgo de volatilidad (skew) se desplaza acompañando al subyacente.

---

## Bloque 8: Estrategias Cuantitativas y Modelación Econométrica

### Pregunta 22: ¿Cómo formularon la Estrategia 1, cómo eliminaron el sesgo de anticipación y cómo cubrieron el delta americano?
* **Respuesta fundamentada:**
  1. **Eliminación del Sesgo de Anticipación (Look-Ahead Purging):**
     Dado que la variable objetivo forward $RV_{t, t+21}^{(m)}$ abarca 21 días hacia el futuro, entrenar modelos de regresión rodante con muestras que lleguen hasta $t$ filtra información de los últimos 20 días. Implementamos una validación walk-forward estrictamente purificada: para predecir en la fecha $t$, el modelo solo se entrena con historia $s \le t - 21$. Bajo este estándar econométrico riguroso, el modelo HAR-RV purificado alcanzó un **QLIKE de 0.1855** y un **RMSE de 15.04 pp**, superando al benchmark EWMA ($\lambda=0.94$, QLIKE 0.2099) y a la volatilidad histórica de 21 días (QLIKE 0.2512).
  2. **Señal Cuantitativa Dinámica:**
     Al 17 de noviembre de 2026, el modelo proyectó causalmente una volatilidad a 21 días de **72.97%**, muy por encima de la IV ATM del mercado a 31 días (**44.02%**), generando una señal $z = \ln(72.97 / 44.02) = +0.505 > 0$ que activó la estrategia `LONG_VOLATILITY_STRADDLE`.
  3. **Cobertura Delta Americana Dinámica:**
     A diferencia de enfoques ingenuos que asumen que un Straddle ATM tiene delta cero o que la Put tiene delta -0.50, calculamos el delta exacto de la Put americana mediante nuestro motor EDP ($\Delta_P = -0.3839$) junto con el delta de la Call ($\Delta_C = +0.6120$). El delta neto de 1 contrato de opciones es de $+22.81$ acciones de NU, el cual se neutralizó exactamente mediante una posición corta de **$h_S = -23$ acciones de NU**.
  4. **Límites Comerciales:**
     Resaltamos que $z > 0$ no asegura ganancias arbitrarias debido a la prima de riesgo de volatilidad (VRP), costos de fricción y slippage de rebalanceo delta. En el régimen de fricción conservador, el subyacente requiere un salto superior al 12% para alcanzar el breakeven.

### Pregunta 23: ¿Cómo se deriva la volatilidad forward entre dos vencimientos en la Estrategia 2 (Calendar Spread)?
* **Respuesta fundamentada:**
  Bajo ausencia de arbitraje de calendario, la varianza total a la madurez $\tau_2$ es la suma de la varianza acumulada hasta $\tau_1$ más la varianza forward esperada entre $\tau_1$ y $\tau_2$:
  $$w(\tau_2) = w(\tau_1) + \sigma_{\text{fwd}}^2 (\tau_2 - \tau_1)$$
  Despejando la volatilidad forward continua:
  $$\sigma_{\text{fwd}} = \sqrt{\frac{w(\tau_2) - w(\tau_1)}{\tau_2 - \tau_1}} = \sqrt{\frac{\sigma_2^2 \tau_2 - \sigma_1^2 \tau_1}{\tau_2 - \tau_1}}$$
  En nuestro análisis entre el vencimiento de 31 días ($\tau_1 = 0.0849, \sigma_1 = 46.11\%$) y 59 días ($\tau_2 = 0.1616, \sigma_2 = 42.52\%$), la volatilidad forward implícita resultó en **38.15%**. El Calendar Spread compra la opción lejana y vende la cercana, explotando el decaimiento acelerado de Theta en la opción corta mientras conserva convexidad en la opción larga.

### Pregunta 24: ¿Por qué decidieron NO fabricar un backtest histórico con ratio de Sharpe para las opciones?
* **Respuesta fundamentada:**
  Fabricar un backtest histórico sin disponer de las cadenas intradía completas del pasado ni de las cotizaciones bilaterales de contratos expirados constituye una **mala práctica metodológica grave**.
  Incurriría en:
  1. **Sesgo de Supervivencia (*Survivorship Bias*):** Trabajar solo con contratos vivos ignora las opciones que expiraron sin valor o fueron ejercidas forzosamente en el pasado.
  2. **Sesgo de Retrospección (*Look-Ahead Bias*):** Simular ejecuciones a `lastPrice` asume liquidez perfecta a un precio histórico que no era una cotización firme disponible.
  3. **Minería de Datos (*Data Snooping*):** Optimizar reglas de salida sobre una sola sección transversal sobreajusta el modelo y promete ratios de Sharpe artificialmente elevados que colapsan en producción real.
  Optamos por la honestidad cuantitativa: validamos el modelo econométrico de volatilidad con walk-forward fuera de muestra estricto sobre el subyacente y analizamos la estrategia mediante análisis contrafactual de escenarios con tres regímenes explícitos de costos de transacción.

---

## Bloque 9: Gobernanza y Recomendaciones para la Entidad

### Pregunta 25: ¿Cuál es la recomendación ejecutiva concreta que debe adoptar el Comité de Riesgos?
* **Respuesta fundamentada:**
  Recomendamos implementar una política de gestión de derivados estructurada en cuatro directrices obligatorias:
  1. **Abandono total de Black-Scholes plano:** Prohibir el uso de una volatilidad única para tarificación y cálculo de VaR; la evidencia demuestra que subestima el riesgo en contratos ITM en más del 54%.
  2. **Adopción de la superficie SVI como estándar de valoración institucional:** Calibrar diariamente la superficie en varianza total con restricciones analíticas para garantizar ausencia de arbitraje mariposa y de calendario.
  3. **Mandato de Revaloración Completa por EDP en Pruebas de Estrés:** Prohibir el uso exclusivo de Griegas de primer y segundo orden para evaluar pérdidas bajo escenarios de estrés severo ($|\Delta S| \ge 10\%$).
  4. **Matriz de Control de Iliquidez y Asignación:** Excluir de la calibración central todo contrato con condicionamiento $\kappa > 3.0$ pp/¢ y exigir un buffer de liquidez para cubrir el riesgo de asignación anticipada en posiciones cortas de Puts americanas.

---

## Bloque 10: Auditoría Cuantitativa Independiente — Segunda Ronda

### Pregunta 26: ¿Por qué existían decrementos de varianza total (arbitraje de calendario) en los nodos calibrados originales y cómo se resolvieron definitivamente?
* **Respuesta fundamentada:**
  En la primera versión de la superficie, la función `surface_iv()` aplicaba la proyección `np.maximum.accumulate` únicamente al interpolar en madureces intermedias, pero cuando $\tau$ coincidía con un vencimiento calibrado devolvía directamente la varianza del corte original. Esto creaba una inconsistencia matemática grave: la superficie era monótona entre nodos, pero no en los nodos mismos (Casos A y B de auditoría), generando saltos artificiales discontinuos al aproximarse a cualquier vencimiento calibrado.
  La solución definitiva unificó la evaluación: para cualquier $k$, se evalúa la secuencia de cortes calibrados y se obtiene la secuencia proyectada monótona $w^*(\tau_i, k) = \max_{j \le i} w_{\text{raw}}(\tau_j, k)$. El interpolador PCHIP temporal evalúa esta secuencia monótona en todo el dominio continuo $\tau \in [\tau_1, \tau_N]$. Dado que en cada nodo PCHIP coincide idénticamente con $w^*(\tau_i, k)$, se garantiza:
  1. $\frac{\partial w}{\partial \tau} \ge 0$ en todos los nodos exactos y puntos intermedios.
  2. Continuidad estricta $C^1$ sin saltos ($|\text{discontinuidad}| < 10^{-6}$).
  3. Registro transparente de las modificaciones introducidas en `svi_slice_parameters.csv`.

### Pregunta 27: ¿Por qué no se puede aplicar la fórmula analítica $g(k)$ de Raw SVI a un spline PCHIP y cómo se valida formalmente la ausencia de arbitraje mariposa en cortes fallback?
* **Respuesta fundamentada:**
  La función $g(k)$ de Gatheral es una derivación analítica exacta de la primera y segunda derivada de la ecuación hiperbólica de Raw SVI. Aplicar esta fórmula a un spline PCHIP por tramos carece de validez matemática. Asimismo, atribuir `100.0%` de no arbitraje a un corte PCHIP sin verificarlo constituía una garantía ficticia.
  En nuestra implementación, los cortes fallback reportan explícitamente `NaN` en `pct_no_butterfly_arb` (indicando que la fórmula SVI no es aplicable) y se someten a un procedimiento numérico riguroso de diferencias divididas de convexidad de precios:
  $$\frac{\Delta^2 C}{\Delta K^2} = \frac{\frac{C(K_{i+2}) - C(K_{i+1})}{K_{i+2} - K_{i+1}} - \frac{C(K_{i+1}) - C(K_i)}{K_{i+1} - K_i}}{\frac{K_{i+2} - K_i}{2}} \ge -\text{tol}$$
  junto con cotas intrínsecas y monotonía de precios. El vencimiento de 3 días (20-nov) y 395 días (17-dic-2027) satisfacen 100% de convexidad, mientras que el corte LEAPS de enero de 2029 (794d) exhibe $89.5\%$ de convexidad debido a una transacción ilíquida en $K=3.0$, lo cual se registra transparentemente como `EMPIRICAL_ANOMALIES_DETECTED`.

### Pregunta 28: ¿Cómo se asegura que las señales de trading no sean cosméticas y determinen efectivamente la estructura de posiciones y resultados simulados?
* **Respuesta fundamentada:**
  Separamos la función de generación de señales (`generate_strategy_signal`) de la función de construcción del portafolio (`build_straddle_portfolio_from_signal`). Las posiciones, flujos de caja y resultados simulados quedan determinados estrictamente por la acción emitida:
  - `LONG_VOLATILITY_STRADDLE`: Abre $+1$ Call, $+1$ Put, delta hedge con $-23$ acciones, y genera el P&L clásico convexo de volatilidad larga.
  - `NO_TRADE`: Establece estrictamente $0.0$ contratos, $0$ acciones, $\$0.00$ de fricción transaccional y $\$0.00$ de P&L bajo todos los escenarios de shock, justificando la inacción por encontrarse el diferencial dentro de la banda neutral de costos ($\pm 5$ pp).
  - `SHORT_VOLATILITY_STRADDLE`: Abre $-1$ Call, $-1$ Put, delta hedge inverso con $+23$ acciones, recolecta la prima inicial y asume pérdidas de cola no acotadas, etiquetado formalmente como una exposición teórica de riesgo asimétrico.
  Esta separación garantiza que cualquier modificación en el pronóstico se traduzca de inmediato en un cambio efectivo en la cartera simulada.

### Pregunta 29: ¿Cómo garantiza el orquestador del pipeline (`run_all.py`) que un proceso con pruebas o etapas fallidas no se presente falsamente como exitoso?
* **Respuesta fundamentada:**
  El orquestador `run_all.py` fue rediseñado bajo una arquitectura de ejecución segura:
  1. Cada etapa crítica cuenta con validaciones post-ejecución sobre sus artefactos generados (existencia de archivos, tamaño mayor a cero, cantidad mínima de filas y verificación de finitud numérica sin valores infinitos).
  2. Si ocurre una excepción en cualquier etapa bloqueante, el pipeline se aborta inmediatamente y finaliza con código de error `sys.exit(1)`.
  3. La suite de pruebas de Pytest se ejecuta como etapa final obligatoria; si reporta cualquier fallo de prueba, el pipeline captura el código de salida no nulo y termina inmediatamente con dicho código de error (`sys.exit(test_exit_code)`).
  4. El banner final de "PIPELINE EXECUTED SUCCESSFULLY" solo se imprime cuando todas las etapas y las 48 pruebas de regresión concluyen con éxito total.
