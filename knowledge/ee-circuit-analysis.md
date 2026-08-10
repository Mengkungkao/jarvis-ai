# AC circuit analysis, impedance, and filters

Impedance is the AC equivalent of resistance, measured in ohms, and
combines resistance with reactance. Capacitive reactance decreases with
frequency: Xc = 1 / (2π × f × C). Inductive reactance increases with
frequency: XL = 2π × f × L. A capacitor blocks DC and passes high
frequencies; an inductor passes DC and blocks high frequencies.

A simple RC low-pass filter (resistor in series, capacitor to ground)
attenuates frequencies above its cutoff frequency f = 1 / (2π × R × C).
Swapping the components gives an RC high-pass filter with the same
cutoff formula. At the cutoff frequency the output is 3 dB down, about
70.7 percent of the input amplitude. Example: 1 kΩ and 100 nF gives a
cutoff of about 1.6 kHz.

An LC circuit resonates at f = 1 / (2π × √(L × C)). At resonance a
series LC circuit has minimum impedance and a parallel LC circuit has
maximum impedance; this is the basis of radio tuning circuits.

Decibels express ratios logarithmically: for voltage, dB = 20 × log10
(Vout / Vin); for power, dB = 10 × log10(Pout / Pin). Minus 3 dB means
half power; 20 dB means 10 times the voltage.

Thevenin's theorem says any linear two-terminal circuit can be replaced
by a single voltage source in series with a single resistor. Norton's
theorem uses an equivalent current source in parallel with a resistor.
Maximum power is transferred to a load when the load resistance equals
the source (Thevenin) resistance, but efficiency is then only 50
percent.

A pull-up resistor holds a signal line at the supply voltage until
something actively pulls it low; a pull-down resistor holds it at
ground. Typical pull-up values are 4.7 kΩ to 10 kΩ. Floating (
unconnected) digital inputs pick up noise and read randomly, which is
why unused inputs need pull-ups or pull-downs.

Duty cycle is the percentage of time a periodic signal is high. PWM
(pulse-width modulation) controls average power by varying duty cycle
at a fixed frequency; it dims LEDs and controls motor speed
efficiently because the switch is always either fully on or fully off.
A hobby servo expects a pulse of 1 to 2 milliseconds every 20
milliseconds; 1.5 ms centers it.

An operational amplifier (op-amp) amplifies the difference between its
two inputs. With negative feedback, a non-inverting amplifier has gain
1 + Rf / Rg, and an inverting amplifier has gain −Rf / Rin. A voltage
follower (gain of 1) buffers a weak source. The golden rules with
negative feedback: no current flows into the inputs, and the output
drives the inputs to the same voltage. A comparator outputs high or low
depending on which input is larger; adding hysteresis (a Schmitt
trigger) prevents oscillation near the threshold.
