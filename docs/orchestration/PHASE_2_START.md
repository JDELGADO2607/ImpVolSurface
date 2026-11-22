# PHASE_START — PHASE_2: solver propio Heston 2D

SHA inicial autorizado `654d1c2d05a0301dc3068cdc34219df3d42d2af7`, condicionado a PHASE_APPROVED de fase1 publicado junto con esta especificación. Rama y worktree Gemini existentes: JDELGADO2607/heston-implementation, PR#5. Coordinación permanece separada, PR#4. No merge ni force-push.

## Objetivo y alcance

Implementar un motor propio de diferencias finitas para puts europeas y americanas bajo Heston clásico, cinco parámetros globales, curva determinista común. No calibrar, no sustituir aún los módulos de producción ni integrar cartera/IV/stress. Conservar QuantLib exclusivamente como referencia de pruebas; el núcleo propio no puede llamar a sus motores de valoración ni copiar sus precios. Reutilizar componentes existentes cuando sean pertinentes, sin modificar SVI histórico ni artefactos de fases0/1.

Método de trabajo elegido H-005A: Modified Craig-Sneyd (MCS), parámetro temporal theta_ADI=1/3, combinado con splitting Ikonen-Toivanen (IT) para el obstáculo americano. theta_ADI y theta de varianza a largo plazo son cantidades distintas. Se trata de una implementación experimental sujeta a auditoría y validación, no de una garantía universal de estabilidad. Documentar cada etapa con referencia a las ecuaciones publicadas; no inventar un esquema ni sustituir IT por clipping final sin multiplicador. Ver [Haentjens e In ’t Hout, secciones3–4](https://arxiv.org/pdf/1309.0110) y [In ’t Hout y Foulon](https://www.math.ualberta.ca/ijnam/Volume-7-2010/No-2-10/2010-02-06.pdf). Si encuentras un impedimento material al método acordado, comunicarlo antes de cambiarlo.

## Formulación y discretización exigidas

Para tau=T−t usar el operador

L V=0.5*v*S²*V_SS+(r(t)−q)*S*V_S+0.5*xi²*v*V_vv+kappa*(theta−v)*V_v+rho*xi*v*S*V_Sv−r(t)*V.

Europea V_tau=LV; americana min(V−g,V_tau−LV)=0, g=max(K−S,0). Inicializar en tau0 con el payoff, no con precios de referencia. IT mantiene una variable auxiliar para el obstáculo; guardar diagnóstico de factibilidad y complementariedad y mostrar su evolución con refinamiento. No afirmar que una sola proyección resuelve exactamente el LCP continuo.

Elegir una malla cartesiana comprensible en S,v, preferiblemente con concentración cerca de K y v0 si es necesaria para precisión. Publicar coordenadas, pesos de primeras/segundas derivadas y término mixto, orientación de ejes y convención de aplanado. Para malla no uniforme no reutilizar fórmulas uniformes. Derivas centrales o unilaterales deben justificarse frente a degeneración y convección. ADI requiere solves por dirección consistentes, signos y contribuciones de frontera incluidos. Rannacher/damping inicial solo si corresponde a un procedimiento publicado y queda explicado.

Fronteras y truncamiento: justificar S0, Smax, v0 y vmax; distinguir v=0 de varianza inicial. En v=0 desaparecen términos proporcionales a v, pero permanecen kappa*theta*V_v y los términos de spot/tasa. No imponer valor intrínseco a toda esa frontera. La opción americana con S=0 y tasas no negativas valeK; la europea usa el descuento residual. Declarar condiciones aproximadas en fronteras altas y estudiar ampliar Smax/vmax sin cambiar a la vez resolución local. No tratar Feller como condición obligatoria para usar el motor.

Tasas: consumir la curva común mediante descuentos/forwards coherentes. r(t)=−d logD(0,t)/dt, evaluado en tiempo calendario t=T−tau y con tratamiento explícito de nudos; no congelar el zero yield r(T) durante toda la vida y llamarlo curva común. Permitir una curva plana explícita en benchmarks. Madurez en años ACT365 y USD por acción. Aceptar xi=0 y v0=theta en el límite de varianza constante; documentar degeneraciones soportadas y fallos explícitos.

Interfaz mínima: precio bruto e información de malla/solver, europea frente a americana, parámetros, spot, strike, madurez y curva. Conservar acceso a la solución de malla para diagnóstico y futuras griegas. Interpolación al punto de valoración explícita y sin overshoot/clipping oculto. No construir infraestructura de plataforma ni una jerarquía innecesaria de modelos.

## Criterios fijados antes de implementar

Fase2 aprueba construcción y pruebas iniciales; **no habilita calibración propia**, que depende de fase3. Para smoke tests, usar spot12.33, q0, vector PoC aprobado y K11/12.33/15, plazos31/94d. En las6 puts europeas y6 americanas el máximo error inicial frente a referencias QuantLib refinadas debe ser <=0.01USD (un tick observado). Es un gate inicial de implementación; el objetivo de validación más amplio de fase3 se fija ahora en0.002USD (un quinto de tick), con error de referencia y truncamiento medidos. No confundir los dos alcances ni presentar0.01 como precisión final del motor.

Precios finitos, condiciones iniciales y fronteras reproducidas; americana>=intrínseco y americana>=europea comparable dentro del error numérico medido. Refinar al menos tres mallas en una muestra ATM/ITM/OTM, separar tiempo de espacio y mostrar un control de truncamiento. No exigir orden teórico observado en el kink sin diagnóstico, pero no aceptar errores que aumenten sin explicación.

Pruebas obligatorias: stencils sobre funciones con derivadas conocidas, incluido término mixto; payoff a T0; v0 degenerado; europea contra AnalyticHestonEngine con integración controlada; americana contra FdHestonVanillaEngine fino; xi0/v0=theta contra BS europeo y EDP americana1D con hipótesis idénticas; rho0 y rho no nulo; aislamiento de salidas y preservación por hashes de fuentes/artefactos históricos. Registrar todos los casos, no solo los favorables. No lanzar pipeline global tras cada cambio.

Entregables: código legible en src/heston/, tests propios, tablas diagnósticas aisladas data/heston/phase2/, informe docs/reports/INFORME_FASE_2_SOLVER_HESTON.md con derivación breve y algoritmo en anexo. Incluir mallas, tiempos, errores USD, excepciones, residual de obstáculo y limitaciones. Reportar qué podría explicar un estudiante en diez minutos. Actualizar documentación de implementación en su rama, sin editar simultáneamente archivos de coordinación; proponer cambios al mapa/contexto mediante referencias de commit.

Publicar un SHA nuevo y PHASE_READY_FOR_AUDIT: archivos modificados, comandos y resultados de tests/experimentos, informe y limitaciones. No avanzar a fase3 sin PHASE_APPROVED. Tres reparaciones como máximo por fase; ante bloqueo fundamental comunicarlo con evidencia, no ajustar tolerancias a posteriori.
