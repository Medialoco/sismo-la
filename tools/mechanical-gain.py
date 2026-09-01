#!/usr/bin/env python3
"""What a mechanical amplifier in front of the sensor would buy this station.

Companion to `tools/sensor-gain.py`, which answers the same question for a
quieter accelerometer. The argument here is different and it rests on one
measured fact: the station's at-rest noise floor is the LSM6DSOX's own
electrical noise, in band (0.00036 g measured against 0.00040 g predicted; see
AGENTS.md, "The seismic band-pass"). Electrical noise is added *after* the
mechanical path, so anything that amplifies ground motion before the sensor
multiplies the signal and not that noise. Amplifying after digitisation does
nothing at all.

Three things are computed, and only the first is pure geometry:

1. `design`  - cantilever dimensions for a target resonance, from beam theory.
2. `gain`    - the amplitude gain a resonance of quality factor Q actually
               delivers to a BROADBAND signal, which is sqrt-like in Q and not
               Q, plus the two haircuts that apply on this station (one axis
               out of three, and site noise that gets amplified too).
3. `rates`   - detections per year, by the same catalog convolution and the
               same refit ground-motion law as `sensor-gain.py`.

Nothing here has been measured on the hardware. `docs/mechanical-gain.md`
states which numbers are calculated and which have to be verified on the board.

Usage:
    python3 tools/mechanical-gain.py [design|gain|rates|all] [--lat L --lon L]
"""
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path

# --- Measured on this station, 2026-09-01 (AGENTS.md) ----------------------
# Equivalent noise bandwidth of the 0.7-12 Hz detector chain. Every "how much
# of a broadband signal does the resonance capture" answer is a ratio against
# this number, so it is the single most load-bearing constant in the file.
DETECTOR_ENBW_HZ = 5.21
# Trigger floor: smallest PGA that ever fired (0.0044 g) divided by the
# measured 1.43x the band-pass bought. Same value sensor-gain.py uses.
TRIGGER_FLOOR_G = 0.0044 / 1.43
# In-band floor at rest, 3-vector mean, and the datasheet prediction for it.
FLOOR_MEASURED_G = 0.00036
FLOOR_PREDICTED_G = 0.00040

# --- Materials -------------------------------------------------------------
# (label, Young's modulus Pa, density kg/m3). Handbook values; the modulus of
# a hardware-store strip is not a controlled quantity, which is why the design
# below is tuned by sliding the clamp rather than trusted from the table.
MATERIALS = {
    "steel":     (200e9, 7850.0),
    "brass":     (100e9, 8500.0),
    "aluminium": (69e9, 2700.0),
}

# (label, material, thickness m, width m, what it is)
STOCK = [
    ("hacksaw blade 12in", "steel", 0.635e-3, 12.7e-3, "300x12.7x0.635 mm, teeth ground off or ignored"),
    ("steel rule 300 mm", "steel", 0.5e-3, 13.0e-3, "thin flexible rule, 0.5 mm class"),
    ("steel strapping", "steel", 0.5e-3, 16.0e-3, "packing band, free from any pallet"),
    ("brass strip", "brass", 0.41e-3, 12.7e-3, "K&S 0.016in x 1/2in"),
    ("aluminium strip", "aluminium", 0.81e-3, 12.7e-3, "K&S 0.032in x 1/2in"),
    ("feeler gauge 0.30", "steel", 0.30e-3, 12.0e-3, "single leaf out of a cheap set"),
]

MODULINO_G = 3.9        # Arduino store, ABX00101, verified 2026-09-01
BEAM_MASS_COEFF = 33.0 / 140.0   # cantilever, effective mass at the tip


# --- 1. Cantilever design --------------------------------------------------

def free_length(f0_hz: float, tip_mass_kg: float, E: float, rho: float,
                t: float, w: float) -> float:
    """Free length of a cantilever whose first bending mode sits at f0.

    k = 3EI/L^3 with I = w t^3 / 12, and the beam's own mass enters as
    (33/140) of it at the tip, so the equation is implicit in L and is solved
    by fixed-point iteration (it converges in a handful of passes because the
    beam is a minority of the moving mass by design).
    """
    omega2 = (2.0 * math.pi * f0_hz) ** 2
    inertia = w * t ** 3 / 12.0
    lin_density = rho * w * t
    L = 0.2
    for _ in range(200):
        m_eff = tip_mass_kg + BEAM_MASS_COEFF * lin_density * L
        L_new = (3.0 * E * inertia / (m_eff * omega2)) ** (1.0 / 3.0)
        if abs(L_new - L) < 1e-9:
            return L_new
        L = 0.5 * (L + L_new)   # damped update, the map is stiff for light tips
    return L


def out_of_plane_hz(L: float, tip_mass_kg: float, E: float, rho: float,
                    t: float, w: float) -> float:
    """The stiff-axis mode, which must stay out of the 0.7-12 Hz band.

    With the blade standing on edge this is the vertical mode, and its inertia
    uses w^3 rather than t^3 -- a factor (w/t)^2 in frequency, i.e. it lands
    decades above the useful one. Computed rather than asserted because it is
    the mode that would quietly put a second peak in the passband if someone
    laid the blade flat instead.
    """
    inertia = t * w ** 3 / 12.0
    m_eff = tip_mass_kg + BEAM_MASS_COEFF * rho * w * t * L
    return math.sqrt(3.0 * E * inertia / (m_eff * L ** 3)) / (2.0 * math.pi)


def tip_stress_mpa(delta_m: float, L: float, t: float, E: float) -> float:
    """Peak bending stress at the root for a given tip deflection."""
    return E * 3.0 * t * delta_m / (2.0 * L ** 2) / 1e6


def cmd_design(f0: float = 4.0) -> None:
    print(f"\n=== 1. Dimensioning, target f0 = {f0:g} Hz "
          f"(Modulino = {MODULINO_G:g} g at the tip) ===\n")
    hdr = (f"{'stock':22s} {'tip mass':>9s} {'free L':>8s} {'beam':>7s} "
           f"{'stiff mode':>11s} {'ring-down tau':>14s}")
    print(hdr)
    print("-" * len(hdr))
    for label, mat, t, w, _note in STOCK:
        E, rho = MATERIALS[mat]
        for added_g in (0.0, 16.1):     # bare Modulino, or Modulino + 16 g
            tip = (MODULINO_G + added_g) / 1000.0
            L = free_length(f0, tip, E, rho, t, w)
            beam_g = rho * w * t * L * 1000.0
            stiff = out_of_plane_hz(L, tip, E, rho, t, w)
            tau20 = 20.0 / (math.pi * f0)
            print(f"{label:22s} {(MODULINO_G + added_g):7.1f} g "
                  f"{L * 1000:6.0f} mm {beam_g:5.1f} g "
                  f"{stiff:8.0f} Hz {tau20:9.2f} s (Q=20)")

    print("\nSensitivity of the tuning, for the 20 g / hacksaw-blade design:")
    E, rho = MATERIALS["steel"]
    t, w = 0.635e-3, 12.7e-3
    tip = 20.0 / 1000.0
    L0 = free_length(f0, tip, E, rho, t, w)
    for dL_mm in (-20, -10, -5, 0, 5, 10, 20):
        L = L0 + dL_mm / 1000.0
        m_eff = tip + BEAM_MASS_COEFF * rho * w * t * L
        f = math.sqrt(3.0 * E * w * t ** 3 / 12.0 / (m_eff * L ** 3)) / (2 * math.pi)
        print(f"   free length {L * 1000:6.1f} mm ({dL_mm:+3d} mm)  ->  "
              f"f0 = {f:5.2f} Hz ({100 * (f / f0 - 1):+5.1f}%)")

    print("\nMechanical headroom, same design:")
    for a_g in (0.01, 0.1, 1.0):
        delta = a_g * 9.81 / (2 * math.pi * f0) ** 2
        print(f"   tip acceleration {a_g:5.2f} g  ->  deflection "
              f"{delta * 1000:6.2f} mm, root stress "
              f"{tip_stress_mpa(delta, L0, t, E):6.1f} MPa")
    print("   (spring steel yields around 1000 MPa, so nothing here is close)")


# --- 2. What the resonance is worth ---------------------------------------

def broadband_gain(Q: float, f0: float, enbw: float = DETECTOR_ENBW_HZ) -> float:
    """Amplitude gain a resonance gives a signal that is broadband over the band.

    A resonance multiplies a *sinusoid at f0* by Q. It does not multiply a
    broadband signal by Q, and conflating the two is the single easiest way to
    overstate this whole idea by a factor of four.

    The integral of |H|^2 over a lightly damped resonance is (pi/2) f0 Q, i.e.
    peak power gain Q^2 times a noise bandwidth of (pi/2) f0/Q. Everything
    outside the peak passes at unity. Against a detector that integrates
    `enbw` hertz, the power gain is therefore

        K = 1 + (pi/2) f0 Q / enbw

    and the amplitude gain is sqrt(K) -- which grows like sqrt(Q), not Q.
    """
    return math.sqrt(1.0 + 0.5 * math.pi * f0 * Q / enbw)


def site_noise_haircut(K_power: float, r: float) -> float:
    """Fraction of the gain that survives amplifying the site noise too.

    The mechanical path lifts ground motion, and ambient ground noise is ground
    motion. Only the sensor's electrical noise is left behind. With r = (site
    noise) / (sensor noise) in the band, the signal-to-noise improvement is

        sqrt(K) * sqrt(1 + r^2) / sqrt(1 + K r^2)

    which saturates at 1/r however large K gets. This is the ceiling on every
    mechanical scheme in the document, and r has never been measured here --
    it is only bounded, because the site could not be separated from zero at
    the current floor.
    """
    return math.sqrt((1.0 + r * r) / (1.0 + K_power * r * r))


# One axis is amplified, the detector reports a 3-vector magnitude. Horizontal
# ground motion is roughly isotropic in azimuth over a wavetrain, so the blade
# sees ~1 horizontal component where the vector magnitude currently sees
# sqrt(H1^2 + H2^2 + V^2). With V ~ 0.5 H that is 1.5 H, hence the ratio below.
MONO_AXIS_FACTOR = 1.0 / 1.5


def cmd_gain() -> None:
    print("\n=== 2. Gain, from Q to something the detector can use ===\n")
    print(f"detector ENBW {DETECTOR_ENBW_HZ:g} Hz, one axis out of three "
          f"(x{MONO_AXIS_FACTOR:.2f})\n")
    for f0 in (3.0, 4.0, 5.0):
        hdr = (f"f0 = {f0:g} Hz   {'Q':>4s} {'ring-down':>10s} {'raw G':>7s} "
               f"{'x1 axis':>8s}" + "".join(f"{'r=' + f'{r:.1f}':>8s}"
                                            for r in (0.1, 0.25, 0.5)))
        print(hdr)
        print("-" * len(hdr))
        for Q in (5, 10, 15, 20, 30, 50):
            G = broadband_gain(Q, f0)
            K = G * G
            tau = Q / (math.pi * f0)
            row = (f"{'':12s}{Q:4d} {tau:8.2f} s {G:7.2f} "
                   f"{G * MONO_AXIS_FACTOR:8.2f}")
            for r in (0.1, 0.25, 0.5):
                row += f"{G * MONO_AXIS_FACTOR * site_noise_haircut(K, r):8.2f}"
            print(row)
        print()
    print("raw G  = broadband amplitude gain of the resonance alone")
    print("x1 axis = after the 3-vector -> 1-axis haircut")
    print("r      = site ground noise / sensor electrical noise, in band.")
    print("         Never measured on this station; the floor measurement")
    print("         bounds it at roughly r < 0.5 and cannot do better.")
    print("         Note the columns: at r = 0.5 the answer barely moves with Q.")

    print("\nFor comparison, the free lever -- a low-rise timber building is")
    print("itself a resonator at 4.2-8.7 Hz with 3-17% damping (Q = 3-17):")
    for f0, Q in ((5.0, 5.0), (5.0, 7.0), (5.0, 10.0)):
        G = broadband_gain(Q, f0)
        print(f"   f0 = {f0:g} Hz, Q = {Q:4.1f}  ->  broadband G = {G:.2f} "
              f"(both horizontals, no build)")


# --- 3. Detections per year ------------------------------------------------

def _load_sensor_gain():
    """Reuse sensor-gain.py rather than re-deriving the catalog convolution."""
    path = Path(__file__).resolve().parent / "sensor-gain.py"
    spec = importlib.util.spec_from_file_location("sensor_gain", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def cmd_band() -> None:
    """Where the acceleration energy of the earthquakes we want actually sits.

    Brune omega-square source, anelastic attenuation along the path and a
    near-surface kappa cutoff -- the three terms that between them decide the
    peak of the acceleration spectrum. Deliberately coarse: the point is to
    place a resonance to within a hertz or two, not to model a waveform.

    Also folds in the detector's own band-pass shape, because a resonance
    placed where the firmware attenuates buys nothing.
    """
    beta = 3.5          # crustal shear velocity, km/s
    stress_drop = 3e6   # Pa
    q_path = 250.0      # anelastic Q for southern California, order of magnitude
    kappa = 0.05        # s, near-surface attenuation, soil site

    def corner_hz(mag):
        m0 = 10.0 ** (1.5 * mag + 9.1)
        return 0.49 * beta * 1000.0 * (stress_drop / m0) ** (1.0 / 3.0)

    def bandpass_gain(f):
        hp = (f * f / (f * f + 0.7 * 0.7))
        lp = 1.0 / (1.0 + (f / 12.0) ** 2)
        return hp * lp          # two poles each side, in power

    print("\n=== 3b. Where to put the resonance ===\n")
    print(f"Brune source (stress drop {stress_drop / 1e6:g} MPa), path Q = "
          f"{q_path:g}, kappa = {kappa:g} s\n")
    freqs = [1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    print(f"{'case':22s} {'fc':>6s}  " + " ".join(f"{f:5.3g}" for f in freqs)
          + "  Hz")
    print("-" * (30 + 6 * len(freqs)))
    best = {}
    for mag, dist in ((3.0, 30.0), (3.5, 40.0), (4.0, 40.0), (4.0, 80.0)):
        fc = corner_hz(mag)
        vals = []
        for f in freqs:
            source = f * f / (1.0 + (f / fc) ** 2)
            path = math.exp(-math.pi * f * dist / (q_path * beta))
            site = math.exp(-math.pi * kappa * f)
            vals.append(source * path * site * math.sqrt(bandpass_gain(f)))
        peak = max(vals)
        best[(mag, dist)] = freqs[vals.index(peak)]
        print(f"M{mag:.1f} at {dist:3.0f} km        {fc:5.1f}  "
              + " ".join(f"{100 * v / peak:5.0f}" for v in vals))
    print("\n(each row normalised to its own peak, in % -- the shape is the point)")
    print("peak of the acceleration spectrum, after the firmware band-pass:")
    for (mag, dist), f in best.items():
        print(f"   M{mag:.1f} at {dist:.0f} km -> {f:.0f} Hz")
    print("\nThe plateau is broad. 4 Hz is the pick: within 2% of the")
    print("band-pass optimum, above where site noise concentrates, and 24")
    print("samples per cycle at the measured 95.3 Hz loop rate.")


def cmd_limits() -> None:
    """How well the station's own floor measurement bounds r, and the draft budget."""
    print("\n=== 2b. How well is r bounded, and by what ===\n")
    sigma_meas = FLOOR_MEASURED_G / 1.5958      # 3-vector mean -> per-axis rms
    print(f"per-axis rms at rest, measured: {sigma_meas * 1e6:.0f} ug")
    print("if the part's true density is (1-e) x the 110 ug/rtHz datasheet "
          "typical:\n")
    print(f"   {'e':>5s} {'sensor rms':>11s} {'implied r':>10s} "
          f"{'ceiling 1/r':>12s}")
    for e in (0.05, 0.10, 0.15, 0.20, 0.25, 0.30):
        sigma_s = (FLOOR_PREDICTED_G / 1.5958) * (1.0 - e)
        ratio2 = (sigma_meas / sigma_s) ** 2 - 1.0
        if ratio2 <= 0:
            print(f"   {e:5.0%} {sigma_s * 1e6:9.0f} ug {'0 (site':>10s} "
                  f"{'unbounded':>12s}")
            continue
        r = math.sqrt(ratio2)
        print(f"   {e:5.0%} {sigma_s * 1e6:9.0f} ug {r:10.2f} {1.0 / r:12.1f}")
    print("\nThe honest reading: the floor measurement is consistent with the")
    print("site contributing nothing, and it stops being able to say so once")
    print("the part is allowed to be 15-20% quieter than its datasheet typical.")
    print("So r < 0.5 is defensible, r = 0 is not provable, and NO mechanical")
    print("scheme can beat 1/r whatever its Q.")

    print("\n=== 2c. Draft budget for the recommended blade ===\n")
    E, rho = MATERIALS["steel"]
    t, w, f0 = 0.635e-3, 12.7e-3, 4.0
    tip = 20.0 / 1000.0
    L = free_length(f0, tip, E, rho, t, w)
    m_eff = tip + BEAM_MASS_COEFF * rho * w * t * L
    area = L * w + 0.041 * 0.02536          # blade face + Modulino face
    print(f"driven area {area * 1e4:.1f} cm2, moving mass {m_eff * 1000:.1f} g, "
          f"Cd = 1.5 assumed")
    for v in (0.03, 0.1, 0.3):
        force = 0.5 * 1.2 * 1.5 * area * v * v
        a_g = force / m_eff / 9.81
        print(f"   draft {v:4.2f} m/s -> {a_g * 1e6:7.0f} ug steady, "
              f"{a_g * 20 * 1e6:8.0f} ug if it gusts at f0 with Q=20 "
              f"(floor is {FLOOR_MEASURED_G * 1e6:.0f} ug)")
    print("\nA barely perceptible 0.1 m/s draft is already half the noise floor")
    print("before any resonant amplification. An enclosure is not optional.")


def cmd_rates(override) -> None:
    sg = _load_sensor_gain()
    events = sg.load_catalog(None, override)
    print("\n=== 3. What each gain is worth, over the real catalog ===\n")
    dists = (10, 30, 50, 100, 160)
    hdr = (f"{'effective gain':>14s} {'floor g':>9s} "
           + " ".join(f"{'M@' + str(d):>6s}" for d in dists)
           + f" {'det/yr (x1..x4)':>17s} {'wait (d)':>10s} {'P(12 d)':>9s}")
    print(hdr)
    print("-" * len(hdr))
    for gain in (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 6.0):
        floor = TRIGGER_FLOOR_G / gain
        mags = " ".join(f"{sg.magnitude_needed(floor, d):6.1f}" for d in dists)
        r_lo = sg.rate_per_year(events, floor, 1.0)
        r_hi = sg.rate_per_year(events, floor, 4.0)
        p_lo = 1 - math.exp(-r_lo * 12 / 365)
        p_hi = 1 - math.exp(-r_hi * 12 / 365)
        tag = "x%.1f" % gain + ("  (today)" if gain == 1.0 else "")
        print(f"{tag:>14s} {floor:9.5f} {mags} "
              f"{r_lo:6.1f} -{r_hi:7.1f}  {365 / r_hi:4.0f}-{365 / r_lo:<5.0f} "
              f"{100 * p_lo:3.0f}-{100 * p_hi:3.0f}%")
    print("\nAdd +-0.45 Mw (1 sigma) to every magnitude; below M3 it is")
    print("extrapolation. The x1..x4 spread is unknown site amplification.")
    print("P(12 d) assumes the gain is in place TODAY, which no build is.")


def main() -> None:
    args = sys.argv[1:]
    override = None
    if "--lat" in args and "--lon" in args:
        override = (float(args[args.index("--lat") + 1]),
                    float(args[args.index("--lon") + 1]))
    wanted = [a for a in args
              if a in ("design", "gain", "band", "limits", "rates")] or ["all"]

    print(f"floor at rest: measured {FLOOR_MEASURED_G:g} g against "
          f"{FLOOR_PREDICTED_G:g} g predicted from the LSM6DSOX datasheet")
    print(f"trigger floor: {TRIGGER_FLOOR_G:.5f} g")
    if "design" in wanted or "all" in wanted:
        cmd_design()
    if "gain" in wanted or "all" in wanted:
        cmd_gain()
    if "band" in wanted or "all" in wanted:
        cmd_band()
    if "limits" in wanted or "all" in wanted:
        cmd_limits()
    if "rates" in wanted or "all" in wanted:
        cmd_rates(override)


if __name__ == "__main__":
    main()
