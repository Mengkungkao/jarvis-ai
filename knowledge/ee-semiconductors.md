# Semiconductors: diodes, LEDs, transistors, regulators

A diode conducts current in only one direction, from anode to cathode.
A standard silicon diode drops about 0.7 volts when conducting; a
Schottky diode drops only about 0.3 volts and switches faster. The
cathode end of a diode package is marked with a stripe. The 1N4148 is a
common small-signal diode; the 1N4007 is a common 1 A rectifier diode.

An LED (light-emitting diode) needs a series resistor to limit current.
Calculate it as R = (Vsupply − Vforward) / Iled. Typical LED forward
voltages: red about 1.8–2.2 V, green and yellow about 2.0–2.4 V, blue
and white about 3.0–3.4 V. A typical indicator LED runs at 5–20 mA.
Example: a red LED on 5 V at 10 mA needs roughly (5 − 2) / 0.010 =
300 ohms; 330 ohms is the common choice. On 3.3 V logic, 150–220 ohms
is typical. The longer LED leg is the anode (positive).

A BJT (bipolar junction transistor) is a current-controlled device with
base, collector, and emitter. In an NPN transistor, a small base current
lets a much larger current flow from collector to emitter; the current
gain is called hFE or beta, typically 100–300 for small transistors.
The base-emitter junction drops about 0.7 V when on. When fully
saturated (switched hard on), the collector-emitter voltage is only
about 0.2 V. Common small NPN transistors are the 2N2222 and BC547;
common PNP parts are the 2N2907 and BC557. To switch a load with an
NPN, put the load between the supply and the collector, tie the emitter
to ground, and drive the base through a resistor (commonly 1 kΩ).

A MOSFET is a voltage-controlled transistor with gate, drain, and
source. An N-channel enhancement MOSFET turns on when the gate-source
voltage exceeds its threshold. For 3.3 V or 5 V control (like Raspberry
Pi or Arduino GPIO), use a logic-level MOSFET whose on-resistance is
specified at Vgs = 2.5 V or 4.5 V, such as the IRLZ44N or AO3400; a
standard MOSFET like the IRF540 will not fully turn on from 3.3 V.
MOSFETs have essentially no gate current when static, but a gate
resistor (about 100 Ω) limits switching spikes and a pull-down resistor
(about 10 kΩ) keeps the MOSFET off when the pin floats.

MOSFETs switch high-current loads efficiently because their on-state
resistance (Rds-on) can be a few milliohms, dissipating P = I² × Rds-on.

A linear voltage regulator like the LM7805 outputs a fixed 5 V from a
higher input and needs about 2 V of headroom (dropout); it dissipates
P = (Vin − Vout) × I as heat, so a 12 V to 5 V conversion at 1 A wastes
7 W and needs a heatsink. The LM317 is an adjustable linear regulator.
The AMS1117-3.3 is a common low-dropout (LDO) regulator for 3.3 V rails.
A switching buck converter steps voltage down at 85–95 percent
efficiency and stays cool where a linear regulator would overheat; a
boost converter steps voltage up. Cheap MP1584 or LM2596 buck modules
are common for powering 5 V projects from 12 V.

A zener diode conducts in reverse above its zener voltage and is used
for simple voltage references and clamping. An optocoupler (like the
PC817) transfers a signal through light, electrically isolating two
circuits, useful for mains isolation and noisy loads.
