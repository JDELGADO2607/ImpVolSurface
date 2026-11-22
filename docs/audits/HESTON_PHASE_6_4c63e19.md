# Fase6 — auditoría focalizada de integración

**PHASE_APPROVED para cálculos e integración**, SHA **4c63e19583c740711fdf001f1ae7e6bd9d99d4b9**, PR5. Cierre7/8pendiente de reconciliar el informe/guion; no otra ronda de implementación6. Fecha22-nov-2026. Extracción limpia publicada, alcance académico y prioridades humanas vigentes.

**Reproducción esencial:** `python run_all.py --heston` termina correctamente en30.1s, sin recalibrar ni ejecutarSVI. Seis tablas financieras regeneradas coinciden con las publicadas a1e-12.6tests focales fase6PASS/3.85s. No campaña de robustez ni repetición de auditorías anteriores.

**Comprobación independiente:** agregaciones qty*100, valores/Greeks por pata y hedge concuerdan con los CSV; reconciliación de6escenarios por patas/acciones hasta~1e-13USD. ReprecioQL semianalítico192para3calls y FDHeston700/280/140para2puts de cartera, incluidas diferencias centrales enS/sigma0y theta: máximo errorprecio puts0.00028933USD, error netodelta~0.02264acciones; el hedge redondeado sigue siendo **−393acciones**. Diferencias máximas gamma puts~4.24e-5por unidad. Resultados de riesgo suficientemente estables para el alcance académico.

| Resultado real | Valor |
| --- | ---: |
| PutHestonMAE,97contratos | 0.02384725USD |
| PutflatamericanoMAE | 0.03738470USD |
| CallHestonMAE,142externas | 0.08729128USD |
| CallflatMAE | 0.05679266USD |
| MAEcombinado239,Heston/flatamericano | 0.06154203/0.04891579USD |
| Valor observado/modelo de opciones | 616.00/596.10169USD |
| Deltaopciones/hedge/residual | 393.21986/−393/0.21986acciones |
| Gamma agregada | 118.23812 |
| Sensibilidadsigma0porpp/thetadiaria | 7.17816/−5.99818USD |
| Capital académico aproximado | 5613.87981USD |
| PnLnulo | 0USD |

**Conclusión financiera defendible:** Heston reduce el MAE de puts respecto al flatamericano aproximadamente36.21%, pero empeora el contrastecalls y la MAEcombinada. No hay mejora88%demostrada en esta comparación. Los escenariosinstantáneos positivos no demuestran beneficio histórico; theta, financiación y fricciones no están incluidos en esosPnLinstantáneos.

**Cierre documental necesario, sin recálculo:** el informe6contiene tabla de primas/Greeks que no coincide con sus CSV, por ejemploCallK14delta−0.1754frente+0.17778002real y primas0.12/0.31frente0.15/0.30. Los totales de JSON/CSV sí son correctos. La tabla de convergencia del texto también difiere de suCSV. El mensaje de entrega afirma mejora>88%y el informe101testsfrente100declarados porGemini. Corregir estos valores antes de la defensa: afecta la explicación financiera, no justifica recalibrar ni rehacer el motor. Ver [encargo de cierre](../orchestration/PHASE_7_8_CLOSEOUT.md).

**Limitaciones para mantener:** margen basado en primas de modelo y regla académica simplificada, no margen regulatorio; theta por acortamiento con curva congelada; Taylor incluye segundo orden enS y primero ensigma0, sin todos los términos cruzados/volga; stress instantáneo sin recalibración ni probabilidad. La cartera usa malla120/60para puts; el contraste fino anterior respalda su precisión en estas patas. Nulo se implementa como identidad de base; el repricio independiente confirma la base. MantenerF4-H2y precisiónIVultracorta de fase5 como limitaciones, no reparaciones adicionales.

Evidencias: [script de datos reales](repro_phase6_4c63e19_real.py), [referencias por pata](HESTON_PHASE_6_4c63e19_reference.csv), [log focal](HESTON_PHASE_6_4c63e19_evidence.txt). Script desde cwd de extracción4c63e19con dependencias aprobadas. No se certifica robustez industrial ni ausencia global de arbitraje. Tras corregir únicamente el documento/guion se revisará su nuevoSHA y se publicará cierre independiente final; revisión humana final/no merge permanecen.
