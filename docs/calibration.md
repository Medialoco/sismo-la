# Calibration via the USGS catalog

This is the heart of the project: turning a cheap sensor into a useful instrument
by leaning on a free, permanent ground truth.

## Principle

At a given station, an earthquake produces a peak ground acceleration (PGA) that
decreases with distance and increases with magnitude. As a first approximation
(simplified attenuation law):

```
log10(PGA) ≈ a·Mw + b·log10(distance) + c
```

We do not know `a, b, c` for this particular sensor in its environment. But USGS
gives us `Mw` and the location (hence the `distance` to LA) of every earthquake.
Each "measured shake ↔ cataloged earthquake" match yields a triple
`(PGA_measured, Mw, distance)`. With enough triples, we invert the relation to
**estimate the magnitude** from a measured PGA:

```
Mw_estimated ≈ a'·log10(PGA) + b'·log10(distance) + c'
```

## Procedure

1. **Bootstrap phase (at launch)** — the device queries USGS for recent
   earthquakes ≥ M3 around LA and shows the "not calibrated" state. Until we have
   enough points, it only provides an indicative magnitude.

2. **Accumulation** — every local shake correlated with a USGS earthquake adds a
   calibration point (persisted to JSON).

3. **Fitting** — least-squares linear regression over the accumulated points. We
   keep quality metrics (RMSE, number of points).

4. **Estimation** — once `N ≥ N_min` points (e.g. 8–10), the device estimates the
   magnitude of shakes not yet present in the catalog (early alert), then corrects
   itself when USGS confirms.

## Correlation window

A local shake is associated with a USGS earthquake if:

- the earthquake is **≤ 160 km** from LA and **≥ M3**;
- the time gap between the local timestamp and the USGS origin time is within a
  window `[0, match_window_s]` accounting for wave travel time and clock drift.

Local triggers **without** a matching USGS earthquake are "noise" candidates →
training set for the Edge Impulse model.

## Robustness

- Distance computed from the USGS coordinates and the (fixed) station ones.
- Outlier rejection (residual > k·RMSE).
- Calibration is **site-specific**: moving the station invalidates the history
  (intentionally: this project is validated only in Los Angeles).
