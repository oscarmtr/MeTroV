def get_interpretation_text():
    return """
        ### 1. LCL: Nivel de Condensación por Ascenso (Lifting Condensation Level)

        *   Es la altura a la que el aire, al ascender y enfriarse, se satura (alcanza el 100% de humedad) y el vapor de agua comienza a condensarse en gotitas.
        *   Marca la **base de las nubes** (generalmente cúmulos).
        *   **¿Qué sucede aquí?** Por debajo de este nivel, el aire es "seco" (no saturado); justo en este nivel, se forma la nube (Yau & Rogers, 1996; Lohmann et al., 2016).

        ### 2. CCL: Nivel de Condensación Convectiva (Convective Condensation Level)
        
        *   El CCL es la altura donde una parcela de aire que asciende, calentada por el sol en la superficie, alcanza el 100% de humedad y el vapor de agua comienza a condensarse (Yau & Rogers, 1996).
        *   **Aspecto visual:** Marca la base plana de las nubes cúmulo (las nubes esponjosas, parecidas al algodón) que típicamente se forman en un día cálido y soleado (Yau & Rogers, 1996).
        *   **Funcionamiento:** El sol calienta el suelo, lo que a su vez calienta el aire directamente por encima. Este aire cálido se vuelve más ligero y flota hacia arriba por sí solo, como un globo aerostático. A medida que asciende, se enfría. Una vez que alcanza la altura exacta del CCL, la humedad invisible en el aire se condensa en gotas de agua visibles, creando una nube (Yau & Rogers, 1996).

        ### 3. CIN: Inhibición Convectiva (Convective Inhibition)

        *   Es la "energía negativa" o barrera que impide que el aire ascienda por sí solo. Usualmente es causada por una inversión térmica (aire cálido sobre aire frío) que actúa como tapa.
        *   Representa la cantidad de energía externa requerida para aplicar (empujar) a la parcela de aire para que cruce esa zona estable y alcance el punto donde pueda ascender por sí sola (Lohmann et al., 2016; Houze, 2014).
        *   **Umbrales** (Houze, 2014):
            *   **Baja:** < 15 J/kg (Fácil de romper, las tormentas se forman temprano).
            *   **Alta:** > 100 J/kg (Es muy difícil que se formen tormentas al menos que haya un forzamiento externo muy fuerte, como un frente frío).

        ### 4. LFC: Nivel de Convección Libre (Level of Free Convection)

        *   Es la altura exacta donde la parcela de aire se vuelve más cálida (y menos densa) que el aire circundante.
        *   Es el "punto de liberación". Una vez que la parcela supera esta altura, ya no necesita ser empujada; comienza a ascender espontáneamente como un globo aerostático debido a su flotabilidad positiva (Iribarne & Godson, 1981).
        *   Si no se rompe la CIN, la parcela nunca alcanza el LFC y no hay tormenta.

        ### 5. CAPE: Energía Potencial Convectiva Disponible (Convective Available Potential Energy)

        *   Es el "combustible" de la tormenta. Mide la cantidad total de energía que la parcela acumula mientras asciende libremente (desde el LFC hacia arriba) siendo más cálida que el entorno.
        *   A mayor CAPE, mayor será la velocidad de ascenso (corriente ascendente) y más intensa podrá ser la tormenta (Lohmann et al., 2016; Houze, 2014).
        *   **Umbrales** (Lohmann et al., 2016; Wallace & Hobbs, 2006):
            *   **0 J/kg:** Estable (sin convección).
            *   **< 1000 J/kg:** Inestabilidad marginal (convección débil).
            *   **1000 - 2500 J/kg:** Inestabilidad moderada (tormentas ordinarias).
            *   **2500 - 4000 J/kg:** Muy inestable (tormentas severas, posible granizo grande o tornados).
            *   **> 4000 J/kg:** Extremadamente inestable.

        ### 6. EL: Nivel de Equilibrio o LNB (Equilibrium Level)
        *(Nivel de Flotabilidad Neutra)*

        *   Es la altura donde la parcela de aire deja de ser más cálida que el entorno. Su temperatura se iguala con la temperatura ambiente y pierde su flotabilidad.
        *   Marca la **cima de la nube** (el yunque del cumulonimbo). Aunque la inercia puede hacer que la nube ascienda un poco más (overshooting top), aquí es donde la nube deja de crecer activamente (Lohmann et al., 2016; Houze, 2014).

        ### 7. Análisis de Capas de Nubes y Formación
        
        Para identificar posibles capas de nubes a partir de un sondeo, se analiza la proximidad de las curvas de Temperatura ($T$) y Punto de Rocío ($T_d$) y las rutas de ascenso de la parcela (Lohmann et al., 2016; Wallace & Hobbs, 2006).

        #### A. Nubes Estratiformes (En capas)
        Para capas de nubes estables (Estratos, Altoestratos), se evalúa la humedad relativa alta:
        *   **Proximidad de curvas:** Es probable que existan nubes donde las líneas de $T$ y $T_d$ están muy cerca o se tocan (Lohmann et al., 2016; Iribarne & Godson, 1981).
        *   **Depresión del punto de rocío:** En la práctica, una depresión ($T - T_d$) de **< 3°C a 5°C** indica usualmente la formación de nubes (Wallace & Hobbs, 2006).
        *   **Grosor:** La capa de nubes se extiende verticalmente mientras estas líneas permanezcan cercanas. Una separación repentina indica aire seco y la cima/base de la nube (Wallace & Hobbs, 2006).

        #### B. Nubes Convectivas (Cúmulos)
        Para nubes formadas por corrientes de aire ascendentes:
        *   **Base de la Nube:** Marcada por el **LCL** (ascenso forzado) o **CCL** (Nivel de Condensación Convectiva, por calentamiento de superficie) (Yau & Rogers, 1996).
        *   **Desarrollo Vertical:** Ocurre a lo largo de la adiabática saturada mientras la parcela sea más cálida que el entorno ($T_{parcela} > T_{entorno}$), lo cual es indicado por un **CAPE** positivo (Lohmann et al., 2016).
        *   **Cima de la Nube:** Teóricamente en el **EL/LNB**, donde la flotabilidad se vuelve neutra. Corrientes ascendentes fuertes pueden penetrar más alto (topes sobrepasados) (Lohmann et al., 2016; Houze, 2014).

        #### C. Capa Límite y Niebla
        *   **Estratocúmulos:** Se encuentran a menudo en la cima de la capa límite planetaria, coronados por una inversión térmica (T aumenta con la altura) y un secado agudo (las líneas se separan) (Wallace & Hobbs, 2006).
        *   **Niebla:** Esencialmente una nube en el suelo. Se indica cuando $T \approx T_d$ en el nivel de presión de superficie (Yau & Rogers, 1996; Lohmann et al., 2016).

        ---

        ### Referencias
        *   Lohmann, U., Lüönd, F., & Mahrt, F. (2016). *An introduction to clouds: From the microscale to climate*. Cambridge University Press.
        *   Houze, R. A., Jr. (2014). *Cloud dynamics* (2nd ed., Vol. 104). Academic Press. https://doi.org/10.1016/C2010-0-66412-6
        *   Wallace, J. M., & Hobbs, P. V. (2006). *Atmospheric science: An introductory survey* (2nd ed.). Academic Press.
        *   Iribarne, J. V., & Godson, W. L. (1981). *Atmospheric thermodynamics*. D. Reidel Publishing Company.
        *   Yau, M. K., & Rogers, R. R. (1996). *A short course in cloud physics* (3rd ed.). Pergamon.
        """
