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

## `uci_raw/` — UCI (AIM-94) diabetes dataset

Self-monitoring records for 70 insulin-treated patients: glucose readings
(with pre/post-meal context), regular / NPH / UltraLente insulin doses, and
meal and exercise events, over several weeks to months each. Source: Kahn, M.,
*Diabetes*, UCI Machine Learning Repository, doi:10.24432/C5T59G (AIM-94 data
set provided by Michael Kahn, MD, PhD, Washington University, St. Louis, MO).

Download and extract (gitignored, ~1 MB):

```
mkdir -p data/uci_raw && cd data/uci_raw
curl -L -o diabetes.zip https://archive.ics.uci.edu/static/public/34/diabetes.zip
unzip diabetes.zip
gzip -dc diabetes-data.tar.Z | tar -x      # creates Diabetes-Data/data-01 ... data-70
```

Then load it with `python -m app.loaders.uci ../data/uci_raw/Diabetes-Data`
(see `backend/README.md`). Data quirks the loader handles: a few lines with a
missing or impossible date (`06-31-1991`), non-numeric values (`3A`, `0Hi`,
`0Lo`), zero or >100-unit insulin doses, and undocumented codes (0, 4, 36, 56).
Paper-record entries have fixed times (08:00, 12:00, 18:00, 22:00), so only
series with real device timestamps are used.
