# M12 proof

M12 is a small deterministic quality gate for historical observations. It normalises UTC timestamps and separates accepted observations from quarantined malformed, duplicate, unavailable-at-cutoff, or unverifiable inputs. It has no market, model, order, or live-trading surface.

The real-world proof runs the fixed T480 `m12_quality_probe.py` fixture through the Forex-owned adapter and retains its result. The fixture contains one accepted record and three quarantine outcomes, proving the working processing path without mutating historical source data.
