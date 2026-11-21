# Evidencia independiente de R3

Los scripts se ejecutan con Python 3.12.6 y las dependencias fijadas por la revisión auditada. Proporcione la ruta de una extracción limpia del commit `3d81ff18cae3a9f8dc74c174015fed17031a8da8`. Use una extracción por ejecución del pipeline y pytest. Los demás controles leen el snapshot; los ensayos de fallo y las exportaciones de stress usan directorios temporales.

~~~text
python surface_probe.py <r3>
python edge_probe.py <r3>
python horizon_probe.py <r3>
python put_probe.py <r3>
python holdout_probe.py <r3>
python controls_probe.py <r3>
python stress_probe.py <r3>
python compare_tables.py <r2> <r3>
python check_artifacts.py <r3_pipeline> pipeline pipeline.log
python check_artifacts.py <r3_pytest> pytest pytest.log
~~~

`resultados.txt` contiene resultados de las ejecuciones independientes y sus unidades se indican en el informe. Para referencias a la auditoría anterior use el commit `855eb1cfbd300ddf488bd02d348883f5eac756b8` como segunda extracción.