# Practical skills and electrical safety

Multimeter usage: measure voltage in parallel across a component with
the probes, measure current in series by breaking the circuit (and
using the fused current input), and measure resistance only with the
component out of circuit or the power off. Continuity mode beeps below
a few ohms and is the fastest way to find broken wires and check
solder joints. Never measure resistance or continuity on a powered
circuit, and never measure current in parallel across a source — that
is a short circuit through the meter.

Soldering: heat the joint (pad and lead together) for a second, then
feed solder into the joint, not onto the iron tip. A good joint is
shiny and cone-shaped (with leaded solder); a cold joint looks dull,
grainy, or balled-up and makes unreliable contact. Typical iron
temperature is about 320–350 °C for leaded solder and 350–380 °C for
lead-free. Keep the tip tinned and clean; flux makes solder flow and
prevents oxidation. Solder wick or a solder sucker removes solder for
rework. Work in a ventilated area and wash hands after handling leaded
solder.

Breadboards: the two long side rails are power rails; the short rows of
five holes are connected together, split by the center groove where ICs
straddle. Breadboards are for prototyping at low frequencies and low
currents (under about 1 A); high current melts breadboard contacts.

ESD (electrostatic discharge) can silently kill MOSFETs, CMOS chips,
and modules; touch grounded metal or wear an ESD wrist strap before
handling bare boards, and store parts in anti-static bags.

Electrical safety limits: current through the body is what kills.
Around 1 mA is perceptible, 10–20 mA causes muscle lock ("can't let
go"), and 30–100 mA and above across the chest can cause fatal heart
fibrillation. Voltages above roughly 50 V are considered dangerous to
touch; treat anything above that with respect, and mains (120/230 V)
as potentially lethal, always.

Mains safety rules: never work on mains wiring live; switch off and
verify dead with a tester. In UK/EU wiring, brown is live, blue is
neutral, and green/yellow is protective earth. Use insulated tools,
keep one hand in your pocket when probing high voltage, and use an RCD
(GFCI) protected outlet for workbench mains equipment. Do not open
switch-mode power supplies or microwave ovens casually: their internal
capacitors can hold lethal charge after unplugging. Discharge large
capacitors through a resistor (not a screwdriver) before handling.

Fire safety: lithium battery fires cannot be put out with water on the
cell chemistry level — use sand, a class D extinguisher, or let it burn
out in a safe place; disconnect power first if possible.

Debugging methodology: check power rails first with a multimeter (is
the supply voltage present and correct at the chip pins?), then check
ground connections, then signals. Most "broken" circuits are a missing
ground, a floating input, reversed polarity, a cold solder joint, or a
dead breadboard contact. Change one thing at a time and re-test.

Reading a datasheet: check the absolute maximum ratings (never exceed
them), the recommended operating conditions, the pinout diagram, and
the typical application circuit — the typical application circuit is
usually the fastest way to a working design.
