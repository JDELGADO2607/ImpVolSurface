# Auditoría cuantitativa independiente del PR #1

**SHA auditado** `855eb1cfbd300ddf488bd02d348883f5eac756b8`  
**Rama** `fix/quant-audit-2026-11`  
**Base del PR al verificarlo** `master`, `e871eab1d3bbf73184e2757448fbc7933acd56fa`  
**Fecha de valoración de la cadena** 2026-11-17. Spot supuesto 12,33 USD, dividendo continuo cero, 100 acciones por contrato.  
**Estado** `AUDIT_COMPLETE_AWAITING_HUMAN_REVIEW`

[PR principal](https://github.com/JDELGADO2607/ImpVolSurface/pull/1) · [Commit y diff de R2](https://github.com/JDELGADO2607/ImpVolSurface/commit/855eb1cfbd300ddf488bd02d348883f5eac756b8) · [Diff completo del PR al SHA auditado](https://github.com/JDELGADO2607/ImpVolSurface/compare/e871eab1d3bbf73184e2757448fbc7933acd56fa...855eb1cfbd300ddf488bd02d348883f5eac756b8)

## Resumen ejecutivo

Gemini confirmó que el SHA corresponde al cierre de R2 y que R3 seguía en desarrollo. Se auditó un archivo Git extraído del SHA confirmado. La proyección corrige dos caídas de varianza total en nodos exactos a log-moneyness forward fijo. La superficie final pierde convexidad en dos vencimientos intermedios, con evidencia reproducible incluso en el tramo común de strikes de los cortes vecinos. Encontré además un put americano cuyo precio cae al ampliar su plazo en un strike soportado. La recomendación técnica provisional es **mantener el PR #1 pendiente de revisión humana**. Las cifras in-sample todavía sirven como diagnóstico de ajuste. Una aprobación para uso de la superficie final requiere validación conjunta en el dominio publicado.

| BLOCKER | HIGH | MEDIUM | LOW |
| ---: | ---: | ---: | ---: |
| 1 | 5 | 3 | 2 |

## Archivos modificados en el commit auditado

- Código y orquestación: `run_all.py`, `src/forecasts.py`, `src/model_comparison.py`, `src/strategies.py`, `src/stress_testing.py`, `src/surface.py`.
- Pruebas: `tests/conftest.py`, `tests/test_no_lookahead.py`, `tests/test_pipeline_error_propagation.py`, `tests/test_surface_and_interpolation.py`.
- Tablas en `outputs/tables/`: `model_comparison_detailed.csv`, `model_comparison_summary.csv`, `strategy1_straddle_scenarios.csv`, `strategy2_calendar_scenarios.csv`, `svi_slice_parameters.csv`.
- Figuras en `outputs/figures/`: `model_comparison_errors.png`, `smile_2d_slices.png`, `strategy1_payoff_scenarios.png`.
- Documentación: `README.md`, `docs/DECISIONES_Y_LIMITACIONES.md`, `docs/GUIA_EXPOSICION_10_MIN.md`, `docs/INFORME_FINAL_REPARACION.md`, `docs/MANUAL_MATEMATICO_COMPLETO.pdf`, `docs/MANUAL_MATEMATICO_COMPLETO.tex`, `docs/PREGUNTAS_DEFENSA.md`, `docs/SEGUNDA_AUDITORIA_PR1.md`.

El commit cambia 26 archivos respecto de `62816f5`. El diff del PR desde la base observada abarca 53 archivos.

## Hallazgos

### B1 · BLOCKER · Mariposas negativas en la superficie final

**Defecto demostrado.** Recalibré desde el CSV publicado con precisión completa y valoré calls usando la CDF normal como implementación independiente de Black–Scholes. Para cada vencimiento evalué tres mallas uniformes, con 121, 241 y 481 strikes en la intersección de los intervalos observados de los cortes vecinos. Con dividendo cero y tasa positiva constante para cada consulta, el call americano coincide con el europeo. Para strikes equiespaciados, una cartera larga de una call en cada extremo y corta de dos calls centrales tiene payoff no negativo, por lo que su prima modelada debe ser no negativa. Para mallas irregulares la prueba equivalente compara pendientes divididas adyacentes.

| Plazo | Intervalo K | Strike central en malla de 481 | Mínimo de curvatura con 121 / 241 / 481 | Prima de la mariposa por acción, malla de 481 |
| --- | --- | ---: | --- | ---: |
| 27,5 días | 10–15 | 14,750000 | −0,03547 / −0,10833 / −0,16708 | −0,00001813 USD |
| 612 días | 5–30 | 20,416667 | −0,13600 / −0,28361 / −0,56841 | −0,00154190 USD |

La curvatura se expresa en USD de precio por USD de strike al cuadrado. Los precios del segundo triplete son aproximadamente 1,30356008, 1,29894283 y 1,29278369 USD. En tripletes irregulares con distancia derecha 1,15 veces la izquierda, las pendientes de call pasan de −0,067971 a −0,069661 a 27,5 días y de −0,088651 a −0,118389 a 612 días. El EDP de puts americanos sobre las mismas IVs también mostró pendientes decrecientes en esos dos tripletes, de 0,938428 a 0,937051 y de 0,914980 a 0,892736. El tamaño de la prima depende del espaciado. El signo persiste con tolerancia de curvatura de −0,0001 y el hallazgo aplica a precios del modelo. La instantánea no permite estimar una ejecución realizable de esa cartera.

A cada plazo fijo, Black–Scholes es creciente en varianza total para k fijo. El máximo de curvas convexas de **precio normalizado en strike forward** preservaría convexidad en los nodos bajo sus hipótesis. El máximo en varianza puede generar cambios de pendiente en k. La presencia de un cambio de pendiente no basta para atribuirle una concavidad, y PCHIP temporal con pendientes dependientes de k no ofrece una preservación general de la convexidad transversal. Los datos también contienen sonrisas crudas con anomalías. La evidencia anterior localiza el defecto en la evaluación final.

**Alternativas y aceptación.** Una interpolación afín en precios normalizados a strike forward constante preserva convexidad si los extremos válidos son convexos. Si además están ordenados punto a punto, la interpolación conserva el orden temporal. Puede perder suavidad temporal en nodos. Una optimización conjunta con restricciones de monotonía, convexidad y calendario permite penalizar desajuste de precios, a cambio de más complejidad y de declarar garantías según la interpolación entre los nodos del problema. Una proyección suave en varianza requiere volver a demostrar las restricciones en precios. Exigir pruebas sobre la superficie publicada en nodos, entre nodos, junto a transiciones de soporte y con refinamiento de strikes. Cuantificar la variación de errores y de las griegas sensibles a curvatura. [Evaluador final](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L620)

### H1 · HIGH · Una extrapolación anterior eleva IV etiquetada como soportada

**Defecto demostrado de trazabilidad.** Para cada strike, evalúe `_evaluate_raw_slice_w(u,k)` para los cortes hasta el tenor consultado y encuentre el `argmax`. A 430 días y K=5, k=−0,956775, domina el corte de 395 días, cuyo mínimo local es −0,482179. La IV sube de 55,6998% a 61,3601%, con Δw=0,0780593. A 31 días y K=10, k=−0,212931, domina el corte de 17 días, con mínimo local −0,162566. La IV sube de 50,9958% a 52,6255%, con Δw=0,00143417. Las dos respuestas marcan `SUPPORTED_LOCAL_GRID` y omiten el origen del ajuste. Eso altera primas y sensibilidades de cualquier consumidor de esos puntos. No cuantifiqué el efecto sobre un portafolio que utilice esos strikes.

**Alternativas y aceptación.** Restringir cada consulta aprobada a un dominio común protegido simplifica la interpretación y reduce cobertura. Ajustar la superficie para que use restricciones temporales solo donde existe soporte exige reglas explícitas en fronteras. Un modo exploratorio puede devolver extrapolación marcada con tenor dominante, intervalo observado y diferencias de IV y w. Repetir ambos contraejemplos y revisar transiciones de dominio antes de certificar el calendario. [Etiquetado y proyección](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L579)

### H2 · HIGH · El corte anómalo de enero de 2029 sigue disponible para valoración

**Defecto demostrado de control de uso.** El CSV de parámetros registra 89,47% de convexidad, 4 de 38 diferencias divididas de call bajo el umbral y 5 violaciones de monotonía de puts en la malla de diagnóstico. El corte sigue en `self.slices`, que alimenta nodos y PCHIP temporal. A K=3 coexistían un último precio call de 10,25 USD con IV 103,88% y un put de 0,04 USD con IV 52,31%. Los últimos precios son asíncronos. La divergencia motiva investigar la cotización y su peso, sin concluir por sí sola que hubiera arbitraje ejecutable. La interpolación de 612 días utiliza el intervalo que termina en ese corte, aunque el diagnóstico no establece qué fracción de la concavidad proviene de cada insumo.

**Alternativas y aceptación.** Una cuarentena reduce el horizonte publicable y permite conservar la cotización para análisis descriptivo. Un reajuste robusto con restricciones económicas podría recuperar cobertura, si se documenta qué contratos cambian de peso y se somete la solución a validación independiente. Probar que la ruta autorizada de valoración y las exportaciones impidan utilizar nodos o regiones en cuarentena. [Registro de cortes](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L403) · [CSV publicado](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/outputs/tables/svi_slice_parameters.csv)

### H3 · HIGH · La métrica fuera de muestra de M4 se calcula con otro estimador

**Defecto demostrado de interpretación.** El LOO retira calls y puts del mismo strike dentro de su vencimiento, ajusta un corte con umbral SVI distinto al de producción y valora mediante IV cruda de dicho corte. La función no reconstruye `VolatilitySurface` ni llama `surface_iv`. El resumen asigna este resultado a la columna M4. Con 197 contratos se obtiene MAE 0,0389 USD, RMSE 0,0649 USD, MAE 2,38 pp de IV y RMSE 4,12 pp. Son métricas de un estimador unidimensional. El MAE de 0,0291 USD para la superficie final proviene del ajuste in-sample en 201 contratos y la reducción 39,6% frente a IV plana corresponde a ese ajuste.

**Alternativas y aceptación.** Etiquetar el diagnóstico existente como LOO por corte preserva su utilidad. Para medir el producto final, retirar el grupo vencimiento–strike, volver a calibrar y llamar al mismo evaluador y política de soporte de producción. Reportar cobertura, USD y pp de IV sobre predicciones comparables y añadir un ejercicio por vencimiento completo para medir interpolación temporal. Las métricas deberán distinguir ajustes, predicciones soportadas y puntos rechazados. [LOO](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L770) · [Asignación a M4](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/model_comparison.py#L157)

### H4 · HIGH · Las pruebas sobrescriben el CSV y la figura de producción del straddle

**Defecto demostrado.** La etapa 7 ejecutó el pronóstico causal de 72,97% y generó un straddle largo con spread de +27,07 pp. La etapa 8 ejecuta pruebas que llaman `analyze_strategy_1_straddle` con pronósticos contrafactuales y los directorios de salida predeterminados. Durante pytest leí la tabla de producción con `SHORT_VOLATILITY_STRADDLE`. Para Base, el P&L cambió de −107,14 a +92,86 USD en shock cero y de +130,21 a −144,49 USD en +25%. Una prueba posterior termina con forecast de 85%, que emite dirección larga y vuelve a escribir la figura con spread de aproximadamente +39,10 pp. El CSV puede recuperar las cifras causales porque el forecast solo interviene en la dirección de la señal. La figura sí incluye el spread en su título. La imagen observada tras la prueba de despacho coincidió byte a byte con la regenerada a 85% (SHA-256 a017f92d11c2…), mientras que la publicada coincide con la regenerada al forecast causal (8e95f2bc29de…). La prueba de fallo de pytest ejecuta las siete etapas otra vez y restauró la figura causal en esta ejecución. La restauración depende del orden y de que esa prueba posterior llegue a volver a ejecutar las etapas.

**Reproducción y aceptación.** Extraer el SHA y ejecutar `python run_all.py` desde la raíz. Capturar los hashes de `strategy1_straddle_scenarios.csv` y `strategy1_payoff_scenarios.png` al cerrar la etapa 7 y después de pytest. También se puede invocar solo la prueba de enlace señal–cartera y comprobar que termina con una salida corta en esas rutas. Usar `tmp_path` para las pruebas que deban exportar, o separar la evaluación de la escritura para las pruebas de señal. Exigir que pytest preserve los hashes de producción y que figura y tabla utilicen el mismo forecast causal. [Pruebas que escriben](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/tests/test_no_lookahead.py#L151) · [Escritura de la tabla y del título](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/strategies.py#L282)

### H5 · HIGH · Un put americano pierde valor al ampliar su plazo

**Defecto demostrado sobre precios del modelo.** K=14,75 USD pertenece al soporte de ambos plazos, con rangos observados de K de 10–16 y 10–15,5. El evaluador devuelve `SUPPORTED_LOCAL_GRID` en ambos. Reproducción desde la raíz con el mismo CSV de B1. Calcular k=ln(K/F(0,T)) por plazo, consultar `surface.surface_iv(k,T)` y valorar un put con `fd_american_price("P",12.33,14.75,T,get_zero_rate(T),iv)`. Contrasté cada valor con un CRR independiente de 1000, 2000 y 4000 pasos, usando en cada nodo el máximo de la continuación y el ejercicio.

| Plazo | IV final | Varianza total | Put EDP | Put CRR 4000 |
| --- | ---: | ---: | ---: | ---: |
| 31 días | 46,15764% | 0,01809489 | 2,46853062 USD | 2,46887421 USD |
| 37 días | 42,26251% | 0,01810587 | 2,46392944 USD | 2,46428529 USD |

El decremento es 0,00460118 USD con EDP y 0,00458892 USD con CRR, del orden de 0,46 USD por contrato. El conjunto de tiempos de ejercicio del put de 37 días contiene el del put de 31 días si ambos se valoran bajo un modelo coherente, con los mismos términos y fechas de ejercicio compartidas. Su supremo de valores de ejercicio debería ser al menos el del put corto. La varianza total crece en este ejemplo incluso a K fijo. Como la valoración americana cambia con la dinámica, la monotonía europea en k fijo no impone el orden requerido de estos precios.

**Alternativas y aceptación.** Una primera opción es verificar los precios americanos finales a K fijo y bloquear las regiones con decrementos que superen el error del motor verificado. Una alternativa es ajustar una dinámica común para ambos horizontes y valorar la malla de puts con ejercicio óptimo en esa dinámica, con coste de modelización y calibración mayor. Exigir monotonía en plazo a K fijo tras la calibración y confirmar los puntos cerca del umbral con mallas o árboles más finos. [Evaluación de IV](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L552) · [Motor americano](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/pricing_american_fd.py#L245)

### M1 · MEDIUM · Dos strikes observados producen un estado de convexidad verificada

**Defecto demostrado de interpretación.** Filtre `tau_days=3` del CSV de IV, donde 4 contratos aportan 2 strikes únicos. El CSV de parámetros reporta 100% y `VERIFIED_EMPIRICAL_CONVEX_BOUNDS`. La función construye 40 puntos de la curva de precio derivada del interpolante. Una diferencia dividida observacional exige tres strikes distintos. El 100% describe una curva modelada en la malla.

**Corrección y aceptación.** Exportar por separado cantidad de observaciones, estado `NOT_TESTABLE` para convexidad empírica y curvatura del interpolante. Comprobar que un vencimiento con dos strikes conserve su clasificación aunque la curva teórica supere las pruebas en la malla. [Validación de malla](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L252)

### M2 · MEDIUM · El pipeline puede aceptar artefactos incompletos o anteriores

**Defecto demostrado.** Llame `_validate_table_file(p,check_finite_cols=["x"])` sobre un CSV `unrelated\n1\n` y otro `x,y\n1,1\n,2\n`. Ambos pasan. El primero omite la columna requerida. El segundo pierde un valor cuando se aplica `dropna`. Con las tablas presentes, sustituí las siete funciones de etapa por funciones vacías y `run_pipeline(raise_on_error=False,run_tests=False)` devolvió 0. Forzando `pytest.main` a retornar 5, se propagó correctamente el 5. El mensaje global de validación incluye figuras ausentes del inventario. Algunas listas de columnas, como `MAE_USD` y `RMSE_USD`, ni siquiera coinciden con el esquema real.

**Corrección y aceptación.** Validar cada archivo con su esquema y política explícita de nulabilidad. Regenerar en un directorio de ejecución vacío o exigir una procedencia verificable del artefacto. Comparar esta solución con comprobar solo la fecha de modificación, que permite publicar datos viejos reescritos. Probar que omitir una figura requerida o dejar una tabla antigua produzca una salida no cero, manteniendo el código de retorno de pytest. [Validador y orquestador](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/run_all.py#L19)

### M3 · MEDIUM · El mínimo de 50 observaciones permite fuga HAR-RV con muestras cortas

**Defecto demostrado fuera de la muestra oficial.** Use 120 observaciones hábiles desde 2025-01-01, `r=np.random.default_rng(3).normal(0,.025,120)`, con `log_ret=r` y `rv_daily=r*r`. Ejecute `fit_har_rv_walk_forward(df,test_window=55)`. Multiplique por 10 ambas columnas en posiciones originales 45 a 54 y recalcule. El primer pronóstico, del 4 de marzo, pasa de 42,91357% a 63,22558%. Los pronósticos hist y EWMA de esa fecha permanecen iguales. La modificación empieza después del origen. El primer índice purgado admite 4 etiquetas maduras. `max(purge_cutoff,50)` incorpora etiquetas posteriores al origen. El CSV oficial tiene 1240 filas y el primer corte purgado calculado admite 928 filas, por lo que esta rama del mínimo queda inactiva en la evaluación publicada.

**Corrección y aceptación.** Aplicar siempre el límite causal y omitir fechas con entrenamiento insuficiente, o rechazar la petición con diagnóstico explícito de muestra. Mantener invariante la predicción del origen al alterar cualquier retorno posterior y exigir cobertura declarada. [Límite de entrenamiento](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/forecasts.py#L85)

### L1 · LOW · El informe de R2 cita P&L que no concilia con la tabla

**Defecto demostrado de documentación.** La tabla de R2 cita −140,70 USD y +109,30 USD para shock cero y +25% del escenario causal. El CSV comprometido publica −107,14 USD y +130,21 USD en régimen Base. En cero, el put paga 33,00 USD con K=12 y spot 12,33, la prima pagada es 133,00 USD y la fricción 7,14 USD. El cálculo concilia con el CSV. El contrafactual corto de 30% dio +92,86 y −144,49 USD, frente a +125,30 y −308,20 USD del cuadro documental. A 46% observé P&L, fricciones y posiciones cero en todos los escenarios.

**Corrección y aceptación.** Generar o verificar la tabla de documentación desde el CSV, fijando el régimen de costos. Congelar cifras y commit juntos antes de su uso académico. [Afirmaciones R2](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/docs/SEGUNDA_AUDITORIA_PR1.md#L164) · [Tabla de escenarios publicada](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/outputs/tables/strategy1_straddle_scenarios.csv)

### L2 · LOW · La regularidad temporal anunciada falla en extrapolación

**Defecto demostrado fuera del intervalo calibrado.** A k=0, evalúe `surface_iv(0,t)` a izquierda y derecha de los extremos con paso de 10⁻⁷ años. En 3 días las pendientes laterales de w son 0,262351 y 0,162060. En 794 días son 0,241743 y 0,210224. La extensión a IV plana conserva el valor y cambia la derivada. Cerca de `t=1e-6` años, el evaluador devuelve w=0 en el umbral y w=10⁻⁶ a `t=1.001e-6`, con `t × iv²` de 2,6261×10⁻⁷ en este último punto. La rama degenerada y el piso de w crean el salto y rompen la identidad entre los campos exportados. Ese plazo queda muy lejos de la cadena usada en los resultados.

**Corrección y aceptación.** Limitar la promesa de regularidad al interior interpolado o diseñar la extensión con derivadas empalmadas. Para consultas de plazo positivo, verificar que `w=t × iv²` y declarar el contrato de uso para t=0. [Umbral y extrapolación](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/surface.py#L604)

## Reproducción independiente y controles

Ejecutar desde una extracción limpia del SHA auditado, con las dependencias fijadas. B1 se reproduce con este código. También sirve para reexaminar los mismos plazos al recibir una nueva revisión.

~~~python
import numpy as np
import pandas as pd
from scipy.special import ndtr
from src.market_data import SPOT_PRICE, get_forward_price, get_zero_rate
from src.surface import VolatilitySurface

data = pd.read_csv("outputs/tables/options_with_iv.csv")
surface = VolatilitySurface(data)
for days, lo, hi in [(27.5, 10.0, 15.0), (612.0, 5.0, 30.0)]:
    t = days / 365
    for n in (121, 241, 481):
        strike = np.linspace(lo, hi, n)
        k = np.log(strike / get_forward_price(t))
        sd = np.sqrt([surface.surface_iv(x, t)["w"] for x in k])
        d1 = -k / sd + sd / 2
        call = SPOT_PRICE * ndtr(d1) - strike * np.exp(-get_zero_rate(t) * t) * ndtr(d1 - sd)
        slopes = np.diff(call) / np.diff(strike)
        curvature = np.diff(slopes) / ((strike[2:] - strike[:-2]) / 2)
        i = np.argmin(curvature)
        butterfly = call[i:i+3] @ np.array([1, -2, 1])
        print(days, n, strike[i+1], curvature[i], butterfly)
~~~

- **Calendario de R2.** Ejecuté por separado el padre `62816f5` desde otro archivo Git. Su evaluación retorna el corte crudo en vencimientos exactos. Reproduje las caídas de varianza en el padre y comprobé que coinciden con las diferencias de varianza cruda de R2. Para 17→24 días con k=−0,163 y 31→37 días con k=0,225, salen −0,0010118433 y −0,0015118838. La evaluación final de R2 arroja 0 en ambos pares. A ±10⁻⁶ años del nodo, las mayores desviaciones observadas frente al valor del nodo fueron 2,5×10⁻¹¹ y 2,9×10⁻¹¹. El PCHIP sobre una secuencia no decreciente mantiene monotonía no estricta en t a k fijo. Para las condiciones de arbitraje europeo con dividendos proporcionales, véase [Gatheral y Jacquier, §2 y §5.3](https://www.ma.imperial.ac.uk/~ajacquie/index_files/GJ%20-%20NoArbSVI.pdf). Esto permite mesetas. La extensión a precios de puts americanos y la regularidad transversal requieren controles propios.
- **Inversión IV.** 201 filas en el CSV publicado. El máximo absoluto de reconstrucción es 2,2118×10⁻⁵ USD por acción. Este residuo mide la consistencia de la inversión con su motor dado. Su magnitud no estima el error de discretización de dicho motor.
- **Puts americanos.** Contrasté el EDP con un árbol CRR independiente de 1000 y 2000 pasos, aplicando el máximo entre continuación y ejercicio en cada nodo. Para (K, días, σ) iguales a (12, 31, 0,45), (15, 90, 0,50) y (20, 794, 0,55), las diferencias absolutas EDP frente a CRR de 2000 fueron 0,000935, 0,000598 y 0,000760 USD. Las primas americanas fueron superiores a sus precios europeos. Estos controles puntuales no certifican una malla completa de precios americanos.
- **Integridad del pipeline.** Reproduje la aceptación de columnas ausentes, valores nulos parciales y tablas anteriores. También verifiqué el retorno 5 ante fallo simulado de pytest. Con la misma inyección de código 5 en el padre, se imprimió una advertencia seguida del mensaje de éxito y el proceso salió con código 0.
- **Ejecución de señal.** Ejecuté el padre con forecast 46% en directorios temporales. Emitió `NO_TRADE` y generó P&L desde −113,43 hasta +209,79 USD, con fricciones de 3,36 a 13,43 USD. Ejecuté R2 con la misma entrada y obtuve posiciones, fricción y P&L nulos. Con 30% emitió la dirección corta y el P&L reconciliado en L1.
- **Fallback.** El padre asignaba 100% a la métrica analítica SVI de los fallbacks. R2 la deja vacía y publica una evaluación numérica. M1 concierne a la interpretación del nuevo estado y H2 a su uso en el evaluador.

## Trazabilidad de los artefactos numéricos

Ejecuté `python -u run_all.py` en la extracción del SHA, con Python 3.12.6, NumPy 2.1.1, SciPy 1.18.0, pandas 2.2.2 y pytest 9.2.0 en Windows. Las siete etapas finalizaron y pytest aprobó 48 de 48 pruebas en 746,80 s. El banner de Python registró éxito tras 1022,9 s. Pytest registró dos advertencias de overflow en el interpolante cúbico de SciPy al recuperar IV de un put y al verificar el fallo intencional del pipeline. PowerShell devolvió 1 al redirigir stderr. Reproduje esa diferencia con un proceso de prueba, cuyo código nativo fue 0 y cuyo envoltorio devolvió 1 si el último comando redirigía el warning. La invocación principal guardó el banner de Python. Comparé las 16 tablas CSV publicadas en `outputs/tables/` con sus regeneraciones. Coincidieron en esquema y valores exactos. El único cambio de bytes en CSV es LF frente a CRLF. Las 9 figuras de `outputs/figures/` coincidieron byte a byte después de la reejecución causal descrita en H4. Esta coincidencia confirma la procedencia numérica para el SHA y el entorno probados. El manual PDF no forma parte de la regeneración del pipeline.

## Limitaciones y decisiones metodológicas

Los últimos precios provienen de una sola cadena asíncrona. La curva del repositorio está rotulada con fechas 17/18 de noviembre de 2026 y usa referencias par. Este análisis usa la curva implementada. Queda pendiente verificar documentalmente el origen contemporáneo de las tasas y su transformación a factores de descuento. [Curva de entrada](https://github.com/JDELGADO2607/ImpVolSurface/blob/855eb1cfbd300ddf488bd02d348883f5eac756b8/src/market_data.py#L21) No hay un panel de opciones para probar rentabilidad histórica, ni cotizaciones sincronizadas para atribuir los defectos del modelo a oportunidades ejecutables. El uso de BS para calls sin dividendos depende de las hipótesis de tasas y ejercicio de este caso. Un escenario de calendario a día 31 que consulta la superficie de origen para el plazo remanente es una hipótesis de roll-down, con riesgo de modelo pendiente de sensibilidad bajo dinámicas alternativas. La estrategia straddle supone liquidación al vencimiento y una cobertura estática. La asignación temprana del put americano, el coste de financiación y el uso de prima como denominador para el corto limitan su interpretación económica. Una comparación de IV con un pronóstico físico de volatilidad realizada justifica una señal hipotética dentro del ejercicio. Las métricas de validación observadas en este informe tienen alcance finito. La revisión de R3 y la revisión complementaria del usuario y ChatGPT quedan pendientes.

## Recomendación técnica provisional

Mantener el PR principal en revisión. La prioridad académica es reproducir y cerrar B1 sobre el dominio que se publicará, condicionar el uso de la superficie a soporte y diagnóstico válidos, y recalcular la métrica fuera de muestra con el evaluador final. El PR de auditoría contiene el informe. La siguiente decisión corresponde al usuario tras la revisión independiente.
