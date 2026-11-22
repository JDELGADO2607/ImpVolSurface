# Cierre independiente Heston — versión académica

**HESTON_IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_REVIEW**. Fecha22-nov-2026. Dictamen técnico provisional: versión funcional y defendible en el alcance académico acordado, con limitaciones explícitas. Aprobación humana definitiva y merge **pendientes**.

SHA definitivo de implementación/documentación: **2a9143ba55f1e17b165fa7132d954227635e6538**, [PR de implementación #5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5), abierto. El cierre solo modifica el informe respecto a4c63e19583c740711fdf001f1ae7e6bd9d99d4b9, cuyo código y resultados fueron examinados y regenerados. Este informe reside en la rama independiente de coordinación/[PR #4](https://github.com/JDELGADO2607/ImpVolSurface/pull/4); su commit documental es distinto del SHA auditado. No merge ni force-push.

## Qué se completó y cómo reproducirlo

Calibración global Heston en puts americanas mediante QuantLib; solver propio2DMCS–IT contrastado; superficie deIVamericana equivalente yIVeuropea; comparación de cuatro modelos; cartera original5patas, griegas/hedge y6stress; tablas/figuras y guion10min. Se conservóSVIhistórico y se aplicó la prioridad humana de mínima complejidad suficiente.

Desde la revisión definitiva, con las dependencias de `requirements-heston.txt` y los inputs/artefactos previos versionados:

```text
python run_all.py --heston
```

Codex ejecutó este comando en extracción limpia del código final4c63e19: terminó en30.1s y las6tablas financieras regeneradas coincidieron con las publicadas a1e-12. No recalibró ni ejecutóSVI. El SHAfinalsolo cambia prosa, por lo que no se repitió ese cálculo ni la suite. Gemini reportó100tests de fases0–6aprobados; Codex ejecutó pruebas focalizadas20de fases2/5y6de integración, además de sus contrastes independientes. No se infiere corrección exclusivamente de pytest.

Fuentes de resultados finales: [comparación239](https://github.com/JDELGADO2607/ImpVolSurface/blob/2a9143ba55f1e17b165fa7132d954227635e6538/data/heston/phase6/models_comparison_summary.csv), [cartera](https://github.com/JDELGADO2607/ImpVolSurface/blob/2a9143ba55f1e17b165fa7132d954227635e6538/data/heston/phase6/portfolio_greeks_and_valuation.csv), [stress](https://github.com/JDELGADO2607/ImpVolSurface/blob/2a9143ba55f1e17b165fa7132d954227635e6538/data/heston/phase6/portfolio_stress_scenarios.csv), [informe/guion10min](https://github.com/JDELGADO2607/ImpVolSurface/blob/2a9143ba55f1e17b165fa7132d954227635e6538/docs/reports/INFORME_FASE_6_INTEGRACION_FINANCIERA.md). Figuras están en `figures/phase5/` y `figures/phase6/` de esa revisión.

## Modelo y calibración que debe explicarse

Curva determinista históricaCMT17-nov-2026,spot12.33,q0,ACT/365. Construcción mediante instrumentos sintéticos y aproximaciones declaradas; no bootstrap exacto de bonos individuales observados. ParámetrosQ, no estimaciones demostradas de dinámica física:

| Parámetro | Valor final |
| --- | ---: |
| v0 | 0.18613777847584 |
| kappa | 2.72546036683707 |
| theta | 0.21367969920004 |
| xi | 0.48178472584297 |
| rho | −0.94980666301298 |
| 2kappa*theta/xi² | 5.01795862 |

**La calibración usa60puts train y SSE SIN ponderar**: suma(P_Am_Heston−P_observado)². Otras22puts son holdout de strikes y15de tres tenores completos37/94/304d.97es el universo de evaluación, no el número de puts usadas para ajustar.142calls son contraste externo. El vectorPoC se conservó por continuidad/materialidad: un refinamiento mejora ligeramente SSE con diferencias de precios train<=0.00184USD; eso no prueba mínimo global, identificación única ni sobreajuste de la alternativa.

El pricer propio resuelve enS/v con MCS e Ikonen–Toivanen; QuantLib es referencia y motor de optimización. IVput es la sigma constante que reproduce el precio americano por EDP1DyBrent; IVcall se obtiene del precio europeoHeston mediante BS. Ninguna es idéntica a sqrt(v0) ni sqrt(theta).

## Resultados y comparación honesta

| Muestra/resultado | Heston | Flat americano44% |
| --- | ---: | ---: |
| MAE97puts USD | 0.02384725 | 0.03738470 |
| RMSE97puts USD | 0.03403627 | 0.05488664 |
| MAE142calls USD | 0.08729128 | 0.05679266 |
| MAE239combinados USD | 0.06154203 | 0.04891579 |
| RMSE239combinados USD | 0.10108714 | 0.08817155 |

Heston reduce MAEputs **36.21%**, pero empeora calls y agregado239. No superioridad global ni mejora88%. MAEputs por partición: train0.02573726, strikeholdout0.02110820, tenorholdout0.02030449USD. La EEPHeston en puts promedia0.02874687USD y máximo0.56725477USD; callsq0/r>=0tienenEEP0en teoría.

Comparación históricaSVI/Heston sobre84puts comunes: MAESVIhistóricoR3~0.06844167 frente Hestonpropio~0.02310925USD. **Las curvas/métodos históricos difieren**: la variación no se atribuye exclusivamente al modelo ni se equipara a validación fuera de muestra. No se recalibróSVIpara esta entrega.

EnIV:88/97puts y140/142calls tienen raíces interiores; grillas descriptivas29/35puts y33/35calls identificadas. Las filas restantes permanecen con estado; unaIV0.01en el extremo del bracket no es evidencia de volatilidad económica1%. Las métricasIV usan88puts y137calls con ambas inversiones identificadas, mientras las métricas de precio conservan todos los contratos.

## Validación numérica y riesgo

Fase3comparó97puts y108precios de regímenes con referencias refinadas; máximo propiofino/QL~0.000546y0.000509USD. ControlesFellerviolado,xi0,v0positivo tendiendoacero, temporal/espacial y fronteras están en auditorías previas. v0=0no tiene referenciaQLdirecta y no se fingió coincidencia. Estas son verificaciones finitas, no demostración global de convergencia/arbitraje ausente.

Enfase5,Codex reprició15puts reales conQLyEDP1Dfina: núcleos31/59d dentro0.00093USD. ReconstrucciónBSindependiente de140calls con residualmáximo~1.53e-8USD. Diferencia máxima de142calls frenteQL192/adaptadorcomún~0.000404USD. El caso3d/K12.5muestra menor precisión: error0.002706USD(QL)aIVpublicada; IV0.43422pasa0.42854al refinar. Se acepta y documenta esa limitación, sin afirmar cumplimiento0.002USDpara cada punto.

Cartera5patas: observado616USD,modelo596.10169USD,mark-to-model−19.89831USD; deltaopciones393.21986,hedge−393acciones,residual0.21986. Gamma118.23812,sensibilidadsigma0porpp7.17816USD,thetadiaria−5.99818USD. Capital5613.87981USD es aproximación académica basada en primas de modelo, no margen regulatorio. Thetaacorta vencimiento con curva congelada; sensibilidadsigma0no es vegaIV.

Codex contrastó las5patas/derivadas conQL: precio máximo de puts difiere0.00028933USD y deltaneta de referencia393.19722mantiene el mismohedge−393. Agregaciones yPnLporpatas se reconcilian hasta~1e-13USD. Stresshedged: nulo0; spot−5%+26.25560;spot+5%+18.53726;sigma0+5pp+34.79703;crisis−20%/+12pp+492.20577;rally+15%/−8pp+97.18078USD.

Son escenarios instantáneos, no rentabilidad histórica/probabilística. Taylorincluye segundoS y primersigma0, sin todos los términos cruzados/volga; sus47.10USDde diferencia en crisis son **residuo de aproximación**, no atribución demostrada a una ganancia pura de convexidad. Los shocksgrandes no prueban inmunidad de la cartera; omiten paso del tiempo, financiación y fricciones.

## Estado de módulos y limitaciones

| Área | Dictamen en alcance académico |
| --- | --- |
| Datos/curva | Aprobados con asincronía/lastPrice y aproximaciones de curva documentadas |
| CalibraciónQglobal | Aprobada para universo fijado; identificación débil/rho cerca del bound |
| Solver2Dy1D | Verificados en dominios ensayados; no precisión uniforme/global |
| IVequivalente | Funcional con noidentificación en fronteras y precisiónultracorta limitada |
| Comparación/cartera/Greeks/stress | Cálculos aprobados; hipótesis y unidades deben conservarse |
| Reproducción esencial | PipelineHeston reproducido; inputs/outputs versionados |
| Defensa10min | Lista con precisiones de lectura indicadas en este informe |
| Revisiónhumana/merge | Pendientes; no merge automático |

F4-H2permanece técnicamente abierto y aceptado por el usuario como limitación de robustez artificial: un gate no verifica todas las cotas europeas bajo manipulación de artefactos; **los precios legítimos sí las cumplen**. No se declara reparado ni se reabre. Otras robusteces industriales quedan fuera por instrucción humana. Se conservan límites menores de interpolación/mallas y falta de garantía paramétrica/global.

Los hallazgosSVIhistóricos no se borran: no se usa su interpolación/proyección en la rutaHeston y se verifican precios directos. Causalidad/HARy otras estrategias históricas no se ampliaron ni se certificaron como backtest; no existe panel de opciones que respalde rentabilidad histórica. El enunciado original46–56no está disponible íntegro: el cumplimiento académico formal se apoya en el mapeo secundario existente y requiere la revisión del estudiante/profesor.

## Precisiones finales para la exposición

El cierre documental corrigió primas/Greeks, signo unitarioCallK14positivo, comparación y stress. Quedan dos expresiones a leer con la precisión anterior: donde el guion diga «pérdida ponderada sobre97puts», explicar **SSEno ponderada sobre60train,97evaluadas**; donde diga «ganancia no lineal pura», explicar **diferencia entre revaloración y Taylor incompleto**. Son residuos editoriales identificados, no cambios numéricos ni motivo para otra ronda. «Óptimo» significa aquí candidato local/conservado, no prueba de óptimo global. El presente informe proporciona la formulación correcta para defensa.

Evidencia independiente y scripts: [fase4](HESTON_PHASE_4_7f51a81.md), [aceptación humana de alcance](HESTON_PHASE_4_7f51a81_ACCEPTED_SCOPE.md), [fase5](HESTON_PHASE_5_b4cb3d6.md), [fase6](HESTON_PHASE_6_4c63e19.md). No se vuelven a ejecutar sus experimentos satisfactorios por un diffsolo documental.

**PHASE_APPROVED8 con observaciones editoriales no bloqueantes.** Objetivo de implementación/cierre académico completado, estado **HESTON_IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_REVIEW**. Congelar revisión2a9143b. Usuario yChatGPTrevisarán independientemente el informe, los resultados yPR5; Codexno sustituye esa decisión ni autoriza merge.
