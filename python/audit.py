"""Replay the event journal and score the calibration honestly.

    python audit.py                    # reads event_log.jsonl
    python audit.py path/to/log.jsonl

Why this exists: `CalibrationModel.rmse` is a *training* residual. It is
computed over the very points the coefficients were fitted on, so it can only
flatter the model, and it uses the earthquake's true catalog distance while the
station in the field has to estimate that distance from the shake itself.

The journal records, for every detection, what the models predicted before they
learned it. Replaying those stored predictions gives prequential residuals: a
genuine out-of-sample error, measured on the operational path. This tool prints
both numbers side by side, and the gap between them is the honest measure of
how optimistic the self-reported figure is.

Note the ordering caveat: prequential scoring is sequential, so the earliest
points are scored by a model that had barely any data. That penalises the model
relative to a held-out split on a mature model. It is the pessimistic bound,
the self-reported RMSE is the optimistic one, and the truth is in between.
"""

from __future__ import annotations

import argparse
import math

import numpy as np

import eventlog


def _rmse(values: list[float]) -> float | None:
    if not values:
        return None
    return float(np.sqrt(np.mean(np.square(values))))


def _fmt(value: float | None, unit: str, digits: int = 2) -> str:
    return "n/a" if value is None else f"{value:.{digits}f} {unit}"


def in_sample_magnitude_rmse(matched: list[dict]) -> tuple[float | None, int]:
    """Refit the amplitude law on every matched point and score it on itself.

    Reproduces what the live model reports, so the comparison below is
    apples-to-apples rather than a difference of datasets.
    """
    rows, targets = [], []
    for record in matched:
        pga, match = record.get("pga_g"), record["match"]
        distance, magnitude = match.get("distance_km"), match.get("magnitude")
        if not pga or pga <= 0 or not distance or distance <= 0 or magnitude is None:
            continue
        rows.append([math.log10(pga), math.log10(distance), 1.0])
        targets.append(magnitude)

    if len(rows) < 3:
        return None, len(rows)

    x, y = np.array(rows), np.array(targets)
    coeffs, *_ = np.linalg.lstsq(x, y, rcond=None)
    return _rmse((y - x @ coeffs).tolist()), len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay the Sismo-LA journal")
    parser.add_argument("journal", nargs="?", default="event_log.jsonl")
    parser.add_argument(
        "--include-synthetic", action="store_true",
        help="also score --replay events. They were synthesized from the very "
             "quakes they are matched to, so the result exercises the code but "
             "measures nothing physical. Off by default, on purpose.",
    )
    args = parser.parse_args()

    records = eventlog.read(args.journal)
    if not records:
        print(f"[audit] no records in {args.journal}")
        print("        The station writes one line per detection; leave it "
              "running to accumulate them.")
        return

    matched = [r for r in records if r.get("match")]
    synthetic = [r for r in matched if r["match"].get("synthetic")]
    real = [r for r in matched if not r["match"].get("synthetic")]

    print(f"[audit] {args.journal}")
    print(f"  detections            {len(records)}")
    print(f"  matched to USGS       {len(matched)}"
          f"  (real {len(real)}, synthetic/replay {len(synthetic)})")
    print(f"  unmatched             {len(records) - len(matched)}")

    if args.include_synthetic:
        scored_set = matched
        if synthetic:
            print("\n  *** --include-synthetic: replay events are SCORED below. "
                  "They were\n  *** generated from the quakes they are matched "
                  "to, so what follows\n  *** exercises the pipeline and "
                  "measures nothing about the sensor.")
    else:
        scored_set = real
        if synthetic:
            print("\n  Synthetic matches come from --replay, where the event was "
                  "generated\n  from the very quake it is matched to. They are "
                  "excluded below: scoring\n  against them measures the "
                  "attenuation law's inverse, not the sensor.\n  Pass "
                  "--include-synthetic to score them anyway.")

    # --- Prequential: what the model predicted BEFORE it saw each point ------
    operational, with_true_distance, distance_log10 = [], [], []
    for record in scored_set:
        prior, match = record.get("prior") or {}, record["match"]
        true_magnitude, true_distance = match.get("magnitude"), match.get("distance_km")

        if prior.get("magnitude_operational") is not None and true_magnitude is not None:
            operational.append(prior["magnitude_operational"] - true_magnitude)
        if prior.get("magnitude_true_distance") is not None and true_magnitude is not None:
            with_true_distance.append(prior["magnitude_true_distance"] - true_magnitude)
        if prior.get("distance_km") is not None and true_distance:
            distance_log10.append(
                math.log10(max(prior["distance_km"], 0.1)) - math.log10(true_distance)
            )

    print("\n  Out-of-sample (prequential: predicted before the point was learned)")
    print(f"    magnitude, operational      {_fmt(_rmse(operational), 'Mw')}"
          f"   n={len(operational)}")
    print("      ^ the honest field number: distance estimated from the shake")
    print(f"    magnitude, true distance    {_fmt(_rmse(with_true_distance), 'Mw')}"
          f"   n={len(with_true_distance)}")
    print("      ^ isolates the amplitude law from distance-estimation error")
    print(f"    distance                    {_fmt(_rmse(distance_log10), 'log10 km')}"
          f"   n={len(distance_log10)}")

    rmse, n = in_sample_magnitude_rmse(scored_set)
    print("\n  In-sample (refit on all points, scored on those same points)")
    print(f"    magnitude                   {_fmt(rmse, 'Mw')}   n={n}")
    print("      ^ what the dashboard reports. Compare it with the first "
          "number above.")

    # --- Noise filter, scored before it learned each label ------------------
    scored = [r for r in records if r.get("p_quake_prior") is not None]
    if scored:
        correct = sum(
            1 for r in scored
            if (r["p_quake_prior"] >= 0.5) == bool(r.get("match"))
        )
        print(f"\n  Noise filter, out-of-sample   {correct}/{len(scored)} correct "
              f"({100.0 * correct / len(scored):.0f}%)")
        print("      ^ chance level is high here: almost every shake is noise, "
              "so\n        always answering 'noise' already scores well. Read "
              "it with that in mind.")

    if len(scored_set) < 8:
        print(f"\n  Only {len(scored_set)} scored matches: too few to conclude anything. "
              "These\n  figures become meaningful after a few dozen confirmed "
              "earthquakes.")


if __name__ == "__main__":
    main()
