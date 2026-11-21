# Auditoria independiente Heston fase 1

SHA d6a369c3b636ee0ddb539ddf1938664b54107c4a, PR #5.
Dictamen PHASE_REJECTED, reparacion focalizada 1/3. La evidencia favorece viabilidad del PoC; el gate numerico y su trazabilidad requieren correccion antes de autorizar solver propio.

## Revision favorable reproducida

Extraccion limpia del SHA. Dieciseis tests fase0+fase1 aprobados en 20,86s.
Curva diaria Python/QuantLib coincide en dias 1–794. Diferencia maxima en 10.000 tiempos continuos entre 0,001 y3 anos 2,63424e-6 en D. Es interpolacion aproximada entre dias en torno a quiebres, aceptable para esta prueba si se declara.
Los siete hashes de inputs coinciden. Particiones y llamadas del objetivo muestran uso de train exclusivamente para ajuste.
Los 97 precios americanos exportados se reprodujeron mediante instanciacion directa de QuantLib, sin clipping del wrapper. Diferencia maxima 8,88e-16 USD, minimo precio menos intrinseco cero.
SSE de cinco arranques reproducidas hasta redondeo, incluyendo minimo local malo del tercer inicio y status2 del cuarto. No se repitio la optimizacion de 20min, pues se comprobaron objetivos finales y evaluacion independiente de precios, sin evidencia de alteracion del optimizador.

| Split | N | MAE publicado reproducido | RMSE |
| --- | ---: | ---: | ---: |
| Train | 60 | 0,02588544 | 0,03799239 |
| Strike holdout | 22 | 0,02108157 | 0,02664796 |
| Tenor holdout | 15 | 0,02064911 | 0,02676854 |
| Calls externas | 142 | 0,08732930 | 0,12811797 |

Con revaloracion fina (tFactor200,x200,v100), MAE train/strike/tenor =0,02580678/0,02109497/0,02046987. La conclusion de ajuste razonable se mantiene.
En el mejor vector Q se reproduce ratio Feller5,0179586 y rho=-0,9498067, a menos de0,001 del limite inferior de busqueda.

## F1-01 HIGH — Presupuesto de precios productivos sin cumplir en refinamiento independiente

src/heston/heston_model.py price_american usa x100/v50; evaluate_grid_convergence comprueba x120/v60. La calibracion usa otra malla x70/v35. El informe denomina media a la malla de produccion, pero son distintas.
La malla conjunta de t,x,v en nueve contratos no demuestra control separado del tiempo. Revalue las 97 puts al vector seleccionado y luego refine los tres mayores cambios.

Contrato NU270617P00017000, K17 y212 dias
- Produccion tFactor100,x100,v50, min50 pasos, P=4,7609336 USD aproximadamente.
- tFactor200,x200,v100, P=4,7625024.
- tFactor400,x200,v100, P=4,7631658.
- tFactor200,x320,v160, P=4,7624936.
- tFactor400,x320,v160, P=4,7631892.
El cambio produccion frente a ultima malla ronda0,002256 USD y supera0,002. El componente temporal domina, a diferencia de lo sugerido por una unica comparacion media/fina conjunta. No se afirma conocer el limite exacto del solver, pero existe evidencia directa contra el presupuesto declarado del precio exportado.
Las97 comparaciones contra tFactor200,x200,v100 solas dan max0,0015688 USD, mostrando por que una referencia mas fina es necesaria para los casos lentos.

Reparacion autorizar malla productiva consistente y refinamiento separado en los puntos mas sensibles, con pruebas que calculen precios en vez de leer solo un CSV. Conservar tolerancia0,002. Revalorar los splits. No repetir todo multistart si los precios y seleccion de candidatos se sostienen bajo malla fina. Comprobar al menos estabilidad de clasificacion por SSE fina de los candidatos cercanos antes de decidir si hace falta optimizar otra vez.

## F1-02 MEDIUM — Informe contiene cifras y conclusiones que exceden la evidencia

docs/reports/INFORME_FASE_1_POC_HESTON.md, secciones3–7.
La tabla por tenor indica8 contratos a3d y13 a794d. CSV y fuente muestran12 y5 respectivamente. A31d reporta MAE0,0205 y EEP0,00135, CSV0,024599 y0,013706. A395d EEP documental0,02785 frente a0,219326 en CSV. Hay precios en tabla de convergencia que tampoco concilian, por ejemplo94d/K9 documental~0,1127 frente a~0,11817 en CSV fino.
Corregir todas las tablas desde salidas reales, incluidas maxima desviacion SVI, timestamps y conteos.
La similitud de v0 entre cuatro starts no prueba identificacion perfecta ni identidad entre sqrt(v0) e IV ATM. Holdout MAE menor que train no certifica ausencia universal de sobreajuste. Son subconjuntos de composicion distinta de una instantanea.
Cuatro candidatos dentro de5% de SSE muestran rango de precios:
- K12/31d 0,450450–0,454416 USD.
- K17/794d 5,588822–5,633856 USD (rango0,045034, punto de diagnostico fuera de la lista LEAPS seleccionada).
Esto contradice la afirmacion de ausencia de impacto predictivo de la falta de identificacion. No prueba inviabilidad del modelo. Reportar dispersion en el dominio usado y limitar conclusiones.

## F1-03 MEDIUM — Diagnosticos economicos pueden pasar sin evaluarse

src/heston/pipeline_phase1.py lineas de shape checks. Solo tres plazos, con convexity_ok=True por defecto cuando el triple tiene strikes irregulares. En esos puntos no se hace la prueba y se exporta aprobacion. Monotonia temporal de puts a strike fijo no tiene prueba de produccion.
src/heston/heston_model.py retorna max(npv,intrinsic) y max(npv,0) pese al informe afirmar ausencia de clipping. En los97 puntos auditados el clipping no altero el resultado. Aun asi no permite usar esa funcion como prueba de cotas del motor.
El gate PASSED depende solo de errores y un CSV de malla; no comprueba los resultados de shape. Excepciones del calibrador se convierten silenciosamente en1e8 y status1 es marcado success. Registrar fallos y distinguir limite de iteraciones de convergencia.
Reparacion usar pendientes divididas para strikes irregulares, estado no evaluable en fronteras, prueba temporal a K fijo con curva comun y datos de precio crudo. Unificar gate con esos diagnosticos, clasificando violaciones segun error numerico observado en vez de ocultarlas.

## Alcance y siguiente paso

No hay evidencia de fuga de holdout al objetivo en el diff. Fuente Treasury del manifiesto se registra con timestamp18:45Z distinto de la transcripcion historica16:20 NY, aunque su hash corresponde al mismo archivo. Corregir procedencia al reconciliar informe.
Prueba semianalitica Heston es aproximacion de integracion numerica, no exactitud de maquina universal. Reservar contraste europeo FDM frente a analitico con tolerancia explicita y documentar esquema ADI realmente usado por QuantLib.

Script [repro_phase1_d6a369c.py](repro_phase1_d6a369c.py) para ejecutar desde raiz de extraccion limpia con PYTHONPATH apuntando a esa raiz. Evidencia [log](HESTON_PHASE_1_d6a369c_evidence.txt).
Reparacion1 acotada a precios/gate/documentacion/diagnosticos. No cambiar seleccion, starts, parametros por tenor ni tolerancias para obtener aprobacion. No iniciar fase2.
