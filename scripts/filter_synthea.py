"""Filter Synthea FHIR R4 bundles down to Type 2 diabetes patients.

Reads every patient bundle in the input directory, keeps patients with a
Condition coded SNOMED CT 44054006 (Type 2 diabetes), and writes a slimmed
bundle per patient containing only the resources GlucoTrack uses:

  - Patient
  - Condition           (diagnoses and medical history)
  - MedicationRequest   (metformin, insulin, ...)
  - Observation         (only the LOINC codes below)

Usage:
    python scripts/filter_synthea.py data/synthea_raw/fhir data/synthea_t2d
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

T2D_SNOMED = "44054006"

LOINC_CODES = {
    "4548-4": "HbA1c",
    "2339-0": "Glucose (blood)",
    "2345-7": "Glucose (serum/plasma)",
    "85354-9": "Blood pressure panel",
    "39156-5": "BMI",
}

# Some MedicationRequests point at a separate Medication resource
# (medicationReference) instead of carrying medicationCodeableConcept.
KEEP_TYPES = {"Patient", "Condition", "MedicationRequest", "Medication"}


def codes(concept, system_substring):
    """Return the codes in a CodeableConcept whose system contains system_substring."""
    if not concept:
        return []
    return [
        c.get("code")
        for c in concept.get("coding", [])
        if system_substring in c.get("system", "")
    ]


def has_t2d(resources):
    return any(
        r["resourceType"] == "Condition" and T2D_SNOMED in codes(r.get("code"), "snomed")
        for r in resources
    )


def keep(resource):
    rtype = resource["resourceType"]
    if rtype in KEEP_TYPES:
        return True
    if rtype == "Observation":
        return any(code in LOINC_CODES for code in codes(resource.get("code"), "loinc"))
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input_dir", type=Path, help="Synthea output/fhir directory")
    parser.add_argument("output_dir", type=Path, help="where to write filtered bundles")
    args = parser.parse_args()

    # Synthea also writes hospitalInformation*/practitionerInformation* bundles;
    # patient bundles are the remaining *.json files.
    bundles = sorted(
        p for p in args.input_dir.glob("*.json")
        if not p.name.startswith(("hospitalInformation", "practitionerInformation"))
    )
    if not bundles:
        sys.exit(f"No patient bundles found in {args.input_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    kept = 0
    obs_counts = Counter()
    med_counts = Counter()
    patients_with = Counter()

    for path in bundles:
        total += 1
        with path.open(encoding="utf-8") as f:
            bundle = json.load(f)
        resources = [e["resource"] for e in bundle.get("entry", [])]
        if not has_t2d(resources):
            continue

        kept += 1
        slim = [r for r in resources if keep(r)]
        medications = {
            f"urn:uuid:{r['id']}": r for r in slim if r["resourceType"] == "Medication"
        }

        seen_codes = set()
        for r in slim:
            if r["resourceType"] == "Observation":
                for code in codes(r.get("code"), "loinc"):
                    if code in LOINC_CODES:
                        obs_counts[code] += 1
                        seen_codes.add(code)
            elif r["resourceType"] == "MedicationRequest":
                med = r.get("medicationCodeableConcept")
                if med is None:
                    ref = r.get("medicationReference", {}).get("reference")
                    med = medications.get(ref, {}).get("code", {})
                med_counts[med.get("text") or "unknown"] += 1
        patients_with.update(seen_codes)

        out = {
            "resourceType": "Bundle",
            "type": "collection",
            "entry": [{"resource": r} for r in slim],
        }
        with (args.output_dir / path.name).open("w", encoding="utf-8") as f:
            json.dump(out, f)

    print(f"Patients scanned:          {total}")
    print(f"Type 2 diabetes patients:  {kept} ({kept / total:.1%})")
    print()
    print("Observations kept (LOINC):")
    for code, name in LOINC_CODES.items():
        print(f"  {code:8} {name:24} {obs_counts[code]:7} obs, "
              f"{patients_with[code]:4} patients")
    print()
    print("Top medications in T2D patients (MedicationRequest count):")
    for name, n in med_counts.most_common(15):
        print(f"  {n:6}  {name}")


if __name__ == "__main__":
    main()
