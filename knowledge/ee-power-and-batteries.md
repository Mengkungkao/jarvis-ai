# Power supplies and batteries

A lithium-ion or LiPo cell is nominally 3.7 V, about 4.2 V fully
charged, and should never be discharged below about 3.0 V or charged
above 4.2 V; violating these limits damages the cell and can cause
fire. LiPo cells must be charged with a proper CC/CV (constant current,
constant voltage) charger; the TP4056 module is a common single-cell
charger. Never leave charging LiPo batteries unattended, and never
charge a swollen or punctured cell.

Battery capacity is measured in milliamp-hours (mAh): a 2000 mAh
battery can supply 2000 mA for one hour, or 200 mA for ten hours,
approximately. Connecting cells in series adds voltage (two LiPo cells
in series give 7.4 V nominal); connecting them in parallel adds
capacity at the same voltage. A "2S" pack means two cells in series.
Series packs need balanced charging so all cells stay at equal voltage.

Common battery chemistries: alkaline AA is 1.5 V non-rechargeable;
NiMH AA is 1.2 V rechargeable, about 2000 mAh; lithium-ion 18650 cells
are 3.7 V, typically 2000–3500 mAh (capacity claims above 3600 mAh on
18650 cells are fake); lead-acid is 12 V (six 2 V cells) for cars and
UPS systems; LiFePO4 is 3.2 V per cell, safer, with long cycle life.

The PiSugar battery boards used with the Whisplay chatbot are LiPo
power supplies with their own charge management; the PiSugar 3 is
1200 mAh and the PiSugar 3 Plus is 5000 mAh.

A Raspberry Pi Zero 2W typically draws 100–400 mA at 5 V; a Raspberry
Pi 5 needs a 5 V 5 A (25 W) USB-C supply for full performance.
Undervoltage on a Pi (below about 4.63 V) triggers the lightning-bolt
warning and can corrupt the SD card; use short thick USB cables and a
proper supply.

USB power: classic USB 2.0 ports supply 5 V at up to 500 mA; USB
chargers commonly provide 1–2.4 A; USB-C Power Delivery negotiates
higher voltages (9, 12, 15, 20 V) for more power.

Fuses protect against overcurrent: a fuse's current rating should be
above the normal load current but below what the wiring can safely
carry. A polyfuse (PTC) resets itself after cooling down. Always fuse
the live/positive side.

Wire gauge matters: thin wires have resistance and drop voltage under
load, causing heat. For hobby electronics, 22 AWG handles about 1 A
comfortably; power wiring for several amps needs 18 AWG or thicker.
Voltage drop across a wire equals current times the wire's resistance.

Ground is the common reference point of a circuit. All grounds in a
multi-supply system must be connected together for signals to be read
correctly (common ground), except when circuits are deliberately
isolated through transformers or optocouplers.
