# Passive components: resistors, capacitors, inductors

The resistor color code digits are: black 0, brown 1, red 2, orange 3,
yellow 4, green 5, blue 6, violet 7, gray 8, white 9. On a four-band
resistor, the first two bands are digits, the third band is the
multiplier (number of zeros), and the fourth band is tolerance. A gold
tolerance band means 5 percent; silver means 10 percent; brown means
1 percent. Example: yellow-violet-red-gold is 4700 ohms (4.7 kΩ) at
5 percent tolerance. Example: brown-black-orange is 10000 ohms (10 kΩ).

Common resistor values follow the E12 series: 10, 12, 15, 18, 22, 27,
33, 39, 47, 56, 68, 82 and their multiples of ten. Resistor power
ratings are commonly 1/8 W, 1/4 W, 1/2 W, and 1 W; always check the
dissipated power P = I² × R stays below the rating with margin.

A capacitor stores energy in an electric field; capacitance C equals
stored charge divided by voltage, C = Q / V, measured in farads. The
energy stored in a capacitor is E = ½ × C × V². Common capacitor types:
ceramic capacitors are small, cheap, non-polarized, good for decoupling;
electrolytic capacitors offer large capacitance but are polarized and
must be connected with correct polarity or they can fail violently;
film capacitors are stable and good for audio and timing.

A 100 nF (0.1 µF) ceramic decoupling capacitor placed close to each IC
power pin filters supply noise; this is standard practice in almost
every circuit. Bulk electrolytic capacitors (10–1000 µF) smooth slower
supply variations.

The RC time constant is tau = R × C. A capacitor charging through a
resistor reaches about 63 percent of the supply voltage after one time
constant and is considered fully charged (over 99 percent) after five
time constants.

An inductor stores energy in a magnetic field and opposes changes in
current; its voltage is V = L × di/dt, with inductance L measured in
henries. The RL time constant is tau = L / R. Inductors are used in
filters, switching power supplies, and RF circuits. When the current
through an inductor is suddenly interrupted, it generates a large
voltage spike; that is why relay and motor coils need a flyback diode
across them to safely absorb the spike.

A transformer transfers AC power between two windings through a shared
magnetic core; the voltage ratio equals the turns ratio:
Vsecondary / Vprimary = Nsecondary / Nprimary. Transformers do not work
with DC.
