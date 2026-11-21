# Auditoria independiente Heston fase 0

SHA auditado 334441842135e8a57f0b47338bd8f0ed515a09e2, publicado en PR #5.
Estado PHASE_REJECTED. Reparacion focalizada 1 de un maximo de 3. Fase 1 no autorizada todavia.

## Evidencia favorable

Extraccion limpia del SHA, QuantLib 1.44 disponible. Siete tests de fase 0 aprobados en 5,43 s.
Pipeline fase 0 regenerado con output_dir aislado, codigo 0. Los trece CSV de primer nivel coinciden exactamente al parsear.
Reconteo 272 puts, 141 stale, 25 cotas violadas, 9 microestructura sensible, 97 seleccionadas.
Los 84 contratos comunes son SELECTED_CLEAN. Split 60/22/15, union de 97 simbolos sin duplicacion. Se conserva SVI.
La seleccion ampliada y la politica ex post son elecciones metodologicas admisibles si se explican sus limites.

## F0-01 HIGH — Bootstrap inconsistente con la curva consumida

src/heston/rates_curve.py, _compute_bootstrap y get_zero_rate.
Los cupones intermedios se extrapolan con los nodos anteriores durante stripping. Al introducir el siguiente nodo y consultar r linealmente interpolada se alteran esos descuentos. La misma curva final no reprecia los bonos.
Verificacion independiente PV=100*c*sum(D(j/2))+100*D(T), c=y/2.

| T | PV nominal 100 | Residuo USD |
| --- | ---: | ---: |
| 1 | 100,000000 | 0 |
| 2 | 99,998739 | -0,001261 |
| 3 | 100,002278 | 0,002278 |
| 10 | 99,990860 | -0,009140 |
| 20 | 99,204864 | -0,795136 |
| 30 | 101,345202 | 1,345202 |

La tabla exportada ya muestra esos residuos. El test omite >10 anos y permite 0,05 USD, aunque se anuncia exactitud. La relevancia de los errores largos para las opciones cortas es limitada, pero la formulacion declarada debe conciliar.
Reparacion permitida preferida elegir UNA interpolacion final, resolver cada nodo con su descuento desconocido incorporado a los cupones y verificar todos los instrumentos. Alternativa aceptable explicitar una aproximacion determinista y eliminar promesas de bootstrap exacto, con error y dominio justificados.
Los CMT son referencias par nocionales. Repricing de instrumentos sinteticos no prueba reproducir cotizaciones individuales.
Para el siguiente gate, usar una curva temporal determinista unica en los motores americanos, no una FlatForward diferente para cada vencimiento.

## F0-02 MEDIUM — Ablacion mezcla motor y curva

src/heston/baseline_pricing.py, lineas 163–166. El valor historico SVI proviene del CSV del motor propio, el valor oficial se calcula con QuantLib. Para aislar tasas se necesita mismo motor, sigma y malla, cambiando solo la curva. Guardar aparte el benchmark publicado R3 y la discrepancia del motor.
Maximo cambio AmericanFlat en tabla 0,00100463 USD, superior al <0,0003 USD afirmado. Diferencia SVI 0,00237429 USD mezcla factores.
Eliminar atribucion causal no probada del sesgo a la funcion objetivo SVI. Armonizacion y soporte tambien cambiaron los precios en R3.

## F0-03 MEDIUM — Dependencia y procedencia reproducibles incompletas

QuantLib 1.44 no esta fijado en un archivo de requisitos de la nueva ruta. El manifiesto escribe 1.44 como literal si importa cualquier version.
Guardar version real y dependencia reproducible, hash de referencia SVI consumida y fuente Treasury versionada o su transcripcion identificada con hash y metodo de recuperacion.
La franja 17–18h es disponibilidad estimada, no timestamp de publicacion exacto verificado. Mantener politica ex post y esa distincion.

## Observaciones metodologicas para gate PoC

La propuesta de 0,002 USD equivale a una quinta parte de 0,01, no un orden de magnitud. La granularidad de precios no constituye evidencia de spread ejecutable. Es presupuesto inicial de error a contrastar con tres mallas.
No adoptar 60 s por arranque como limite de aprobacion rigido sin medir coste. Registrar tiempo, evaluaciones y factibilidad.
No restringir rho<=0 como condicion economica universal. Proponer rango que incluya correlacion positiva o justificarlo a priori.
La brecha relativa 30% no se usara sola porque diverge cuando MAE train es pequeno y muestras tienen composicion diferente. Reportar MAE/RMSE por split, cobertura y benchmark comun. Fijar presupuesto antes de calibrar.
No exigir proteccion ATM que el split no implementa. La seleccion determinista de strikes es admisible si se describe fielmente.
Calibracion Q global y calls externas siguen vigentes.

## Reproduccion

Desde extraccion limpia ejecutar python -m pytest tests/test_heston_phase0.py -q.
Ejecutar run_phase0_pipeline(output_dir='audit_regenerated') y comparar CSV con data/heston.
Ejecutar el script adjunto repro_phase0_3344418.py para los residuos de la curva.

Aceptar una nueva entrega solo despues de corregir F0-01, separar la ablacion y completar trazabilidad. No desarrollar aun el solver ni calibracion Heston.
