def get_interpretation_text():
    return """
        ### 1. LCL: Lifting Condensation Level

        *   It is the height at which the air, upon rising and cooling, becomes saturated (reaches 100% humidity) and water vapor begins to condense into droplets.
        *   It marks the **cloud base** (usually cumulus).
        *   **What happens here?** Below this level, the air is "dry" (unsaturated); right at this level, the cloud forms (Yau & Rogers, 1996; Lohmann et al., 2016).

        ### 2. CCL: Convective Condensation Level
        
        *   The CCL (Convective Condensation Level) is the height where a rising parcel of air, heated by the sun at the surface, reaches 100% humidity and water vapor begins to condense (Yau & Rogers, 1996).
        *   **What it looks like:** It marks the flat base of cumulus clouds (the fluffy, cotton-like clouds) that you typically see forming on a warm, sunny day (Yau & Rogers, 1996).
        *   **How it works:** The sun heats the ground, which in turn heats the air directly above it. This warm air becomes lighter and floats upward on its own, just like a hot air balloon. As it rises, it cools down. Once it reaches the exact height of the CCL, the invisible moisture in the air condenses into visible water droplets, creating a cloud (Yau & Rogers, 1996).

        ### 3. CIN: Convective Inhibition

        *   It is the "negative energy" or barrier that prevents air from rising on its own. It is usually caused by a thermal inversion (warm air over cold air) acting as a lid.
        *   It represents the amount of external energy required to apply (push) to the air parcel so it can cross that stable zone and reach the point where it can rise on its own (Lohmann et al., 2016; Houze, 2014).
        *   **Thresholds** (Houze, 2014):
            *   **Low:** < 15 J/kg (Easy to break, storms form early).
            *   **High:** > 100 J/kg (It is very difficult for storms to form unless there is a very strong external forcing, like a cold front).

        ### 4. LFC: Level of Free Convection

        *   It is the exact height where the air parcel becomes warmer (and less dense) than the surrounding air.
        *   It is the "release point". Once the parcel exceeds this height, it no longer needs to be pushed; it starts rising spontaneously like a hot air balloon due to its positive buoyancy (Iribarne & Godson, 1981).
        *   If the CIN is not broken, the parcel never reaches the LFC and there is no storm.

        ### 5. CAPE: Convective Available Potential Energy

        *   It is the storm's "fuel". It measures the total amount of energy the parcel accumulates while rising freely (from the LFC upwards) being warmer than the environment.
        *   The higher the CAPE, the faster the ascent velocity (updraft) and the more intense the storm can be (Lohmann et al., 2016; Houze, 2014).
        *   **Thresholds** (Lohmann et al., 2016; Wallace & Hobbs, 2006):
            *   **0 J/kg:** Stable (no convection).
            *   **< 1000 J/kg:** Marginal instability (weak convection).
            *   **1000 - 2500 J/kg:** Moderate instability (ordinary storms).
            *   **2500 - 4000 J/kg:** Very unstable (severe storms, possible large hail or tornadoes).
            *   **> 4000 J/kg:** Extremely unstable.

        ### 6. EL: Equilibrium Level (or LNB)
        *(Level of Neutral Buoyancy)*

        *   It is the height where the air parcel stops being warmer than the environment. Its temperature equalizes with the ambient temperature and it loses its buoyancy.
        *   It marks the **cloud top** (the anvil of the cumulonimbus). Although inertia may cause the cloud to rise a bit more ("overshooting top"), this is where the cloud stops growing actively (Lohmann et al., 2016; Houze, 2014).

        ### 7. Cloud Layers & Formation Analysis
        
        To identify potential cloud layers from a sounding, the proximity of Temperature ($T$) and Dewpoint ($T_d$) curves and parcel ascent paths is analyzed (Lohmann et al., 2016; Wallace & Hobbs, 2006).

        #### A. Stratiform Clouds (Layered)
        For stable cloud layers (Stratus, Altostratus), high relative humidity is assessed:
        *   **Proximity of curves:** Clouds likely exist where the $T$ and $T_d$ lines are very close or touching (Lohmann et al., 2016; Iribarne & Godson, 1981).
        *   **Dewpoint Depression:** In practice, a depression ($T - T_d$) of **< 3°C to 5°C** usually indicates cloud formation (Wallace & Hobbs, 2006).
        *   **Thickness:** The cloud layer extends vertically as long as these lines remain close. A sudden separation indicates dry air and the cloud top/base (Wallace & Hobbs, 2006).

        #### B. Convective Clouds (Cumulus)
        For clouds formed by rising air currents:
        *   **Cloud Base:** Marked by the **LCL** (forced ascent) or **CCL** (Convective Condensation Level, from surface heating) (Yau & Rogers, 1996).
        *   **Vertical Development:** Occurs along the saturated adiabat as long as the parcel is warmer than the environment ($T_{parcel} > T_{env}$), indicated by positive **CAPE** (Lohmann et al., 2016).
        *   **Cloud Top:** Theoretically at the **EL/LNB**, where buoyancy becomes neutral. Strong updrafts may penetrate higher (overshooting tops) (Lohmann et al., 2016; Houze, 2014).

        #### C. Boundary Layer & Fog
        *   **Stratocumulus:** Often found at the top of the planetary boundary layer, capped by a temperature inversion (T increases with height) and a sharp drying (lines separate) (Wallace & Hobbs, 2006).
        *   **Fog:** Essentially a cloud on the ground. Indicated when $T \\approx T_d$ at the surface pressure level (Yau & Rogers, 1996; Lohmann et al., 2016).

        ---

        ### References
        *   Lohmann, U., Lüönd, F., & Mahrt, F. (2016). *An introduction to clouds: From the microscale to climate*. Cambridge University Press.
        *   Houze, R. A., Jr. (2014). *Cloud dynamics* (2nd ed., Vol. 104). Academic Press. https://doi.org/10.1016/C2010-0-66412-6
        *   Wallace, J. M., & Hobbs, P. V. (2006). *Atmospheric science: An introductory survey* (2nd ed.). Academic Press.
        *   Iribarne, J. V., & Godson, W. L. (1981). *Atmospheric thermodynamics*. D. Reidel Publishing Company.
        *   Yau, M. K., & Rogers, R. R. (1996). *A short course in cloud physics* (3rd ed.). Pergamon.
        """
