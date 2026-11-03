# GlucoTrack data

## `synthea_t2d/` — Synthea Type 2 diabetes patients (FHIR R4)

85 patients, one JSON bundle each (~40 MB total). Each bundle has been slimmed
to the resources the app uses:

| Resource | Used for |
|---|---|
| Patient | demographics (dashboard header) |
| Condition | diagnoses and medical history |
| MedicationRequest + Medication | prescriptions (metformin, insulin, lisinopril, ...) |
| Observation | only LOINC 4548-4 (HbA1c), 2339-0 / 2345-7 (glucose), 85354-9 (BP panel), 39156-5 (BMI) |

Note: some MedicationRequests use `medicationReference` (`urn:uuid:<id>`)
pointing to a Medication resource in the same bundle instead of
`medicationCodeableConcept`. Loaders must handle both.

### Summary of the generated data

- 1000 adults generated, 85 (8.5%) have Type 2 diabetes (SNOMED 44054006)
- All 85 have HbA1c, blood glucose (2339-0), BP and BMI observations
- 39 also have serum/plasma glucose (2345-7)

## How to regenerate

Requires Java 17+ (Synthea does not run on Java 11).

1. Download `synthea-with-dependencies.jar` from
   https://github.com/synthetichealth/synthea/releases into `tools/`.
2. Generate (seeds and reference date are fixed, so output is reproducible):

   ```
   cd tools
   java -jar synthea-with-dependencies.jar -p 1000 -s 42 -cs 42 -r 20261101 -a 18-85 \
     --exporter.baseDirectory ../data/synthea_raw \
     --exporter.fhir.export true \
     --exporter.hospital.fhir.export false \
     --exporter.practitioner.fhir.export false \
     --generate.only_alive_patients true \
     Massachusetts
   ```

   Takes about 5 minutes and writes ~4 GB to `data/synthea_raw/` (gitignored).
3. Filter:

   ```
   python scripts/filter_synthea.py data/synthea_raw/fhir data/synthea_t2d
   ```
