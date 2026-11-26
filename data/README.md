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

## `shanghai_raw/` — Shanghai T2DM continuous glucose monitoring

Real-life CGM readings every 15 minutes for 3-14 days, with diet records and
insulin / oral medication administrations, from 100 people with Type 2
diabetes (109 files; a few people have two monitoring periods). Source: Zhao,
Q. et al., *Chinese diabetes datasets for data-driven machine learning*,
Scientific Data 10, 35 (2023), doi:10.1038/s41597-023-01940-7. Data:
doi:10.6084/m9.figshare.c.6310860, CC BY 4.0. The Type 1 files in the same
download are not used.

Download and extract (gitignored, ~4 MB):

```
mkdir -p data/shanghai_raw && cd data/shanghai_raw
curl -L -o diabetes_datasets.zip https://ndownloader.figshare.com/files/42966622
unzip diabetes_datasets.zip          # creates Shanghai_T2DM/ with one .xls/.xlsx per period
```

Then load it with `python -m app.loaders.shanghai ../data/shanghai_raw/Shanghai_T2DM`
(see `backend/README.md`). Things to know about the files:

- Column positions are stable, but header text varies between files (some are
  only in Chinese), so the loader checks the start of the English headers.
- Use the insulin columns in each file, not the summary sheet, to tell who
  received insulin: 11 files whose summary lists no insulin do record doses.
- 280 diet cells say "data not available"; they are kept as meals with no
  description, since the meal time is still known.
- Diet text is in English (column `Dietary intake`) and Chinese (`饮食`); only
  the English column is used.

## How the sources are combined

The three datasets describe different people. Synthea gives each patient a
clinical record (FHIR R4). The UCI and Shanghai series are attached to
Synthea patients **for demonstration only**: they are not real observations
of those patients. Every glucose, insulin and meal row keeps a `source`
column (`fhir`, `uci`, `cgm`, `user`), and the FHIR API marks UCI and
Shanghai readings as "paired with a synthetic patient for demonstration".

### Pairing

| Source | Attached to | Patients |
|---|---|---|
| Synthea (FHIR) | itself | all 85 |
| UCI | Synthea patients with an insulin prescription | 27 |
| Shanghai CGM | Synthea patients with no insulin prescription; only Shanghai people who received no insulin | 41 |

Each series goes to one patient, in a fixed order, so the pairing is the same
on every run. The other 17 patients have only Synthea lab glucose.

### Units

| Measure | Stored as | Synthea (FHIR) | UCI | Shanghai CGM |
|---|---|---|---|---|
| Glucose | mg/dL | `valueQuantity` in mg/dL (LOINC 2339-0, 2345-7) | mg/dL, as recorded | mg/dL (column `CGM (mg / dl)`) |
| Insulin | units | – | units | not stored (only non-insulin people are used) |
| Meals | description, carbs g, kcal | – | size only ("Larger than usual meal") | food text, e.g. "Rice 150 g" |
| HbA1c | % | `valueQuantity` (LOINC 4548-4) | – | – |
| BMI | kg/m2 | `valueQuantity` (LOINC 39156-5) | – | – |
| Blood pressure | mm[Hg] | panel 85354-9 split into systolic 8480-6 and diastolic 8462-4 | – | – |

No dataset needs a unit conversion: all glucose already arrives in mg/dL.
The only conversion is for data sent to `POST /fhir/Observation`, which
accepts mmol/L and stores mg/dL (mmol/L x 18.016, from glucose's molar mass of
180.16 g/mol).

Code mappings:

- UCI glucose codes become a meal context: 58 fasting (pre-breakfast); 60,
  62, 64 before meal; 59, 61, 63 after meal; 48 and 57 unspecified. Insulin
  codes become a type: 33 short (Regular), 34 intermediate (NPH), 35 long
  (UltraLente). Codes 65 and 69-72 (hypoglycemia symptoms, exercise, special
  events) are not stored.
- Shanghai CGM has no meal context. Finger-stick glucose, ketones and
  oral-medication columns are not stored.

### Validation

Rows are checked with Pydantic models before they are stored; invalid rows
are counted and skipped:

- Glucose must be 20-600 mg/dL (the range of home meters and CGM sensors).
- Insulin doses must be more than 0 and at most 100 units.
- UCI series need records on at least 14 days, and at least 80% of records
  with real device times. Rows at 08:00, 12:00, 18:00 or 22:00 are treated as paper-log
  entries.
- Shanghai series need records on at least 7 days. Only the longest file per
  person is used.

### Dates and times

- All times are stored as the patient's local clock time with no timezone,
  so time-of-day patterns ("high after dinner") read correctly.
- Synthea times carry a US Eastern offset (-04:00 or -05:00). The offset is
  dropped and the clock time kept. The FHIR API adds the offset back from
  `GLUCOTRACK_TIMEZONE` (default `America/New_York`).
- Synthea uses reference date 2026-11-01. Each UCI and Shanghai series is
  shifted by a whole number of days so that its last reading falls on that
  date (`--anchor` to change it). Time of day and the gaps between readings
  are unchanged, so the most recent 14 days line up with the Synthea record.
- UCI series come from 1988-1991 and Shanghai series from 2020-2022, so the
  shifted dates are not the dates the readings were taken.
