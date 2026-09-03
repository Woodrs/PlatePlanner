# PlatePlanner

Laboratory **liquid-transfer planner** for **Tempest**, **Bravo**, and **Floi8**.
Plan volume transfers on interactive plate schematics and export instrument CSVs.

> **Tempest** supports **volume mode** and **concentration mode** (final-volume
> basis). Bravo and Floi8 remain volume-only in this release.

## Requirements

- Python 3.10+
- See `requirements.txt` / `pyproject.toml`

## Setup

```bash
cd PlatePlanner
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Editable install (optional):

```bash
pip install -e ".[dev]"
```

## Run the app

From the repository root (so `plateplanner` is importable):

```bash
streamlit run plateplanner/ui/app.py
```

Or after `pip install -e .`:

```bash
PYTHONPATH=. streamlit run plateplanner/ui/app.py
```

Open the URL Streamlit prints (typically http://localhost:8501).

**UI flow:** choose an instrument in the sidebar → **plan** → **review**
(interactive Plotly plate maps) → **download CSV**. Demo data is built in on
each page. On the Tempest page, switch **Planning mode** between Volume and
Concentration.

## Run tests

```bash
pytest
```

## Instruments

| Instrument | What it plans | Export |
|------------|---------------|--------|
| **Tempest** | Variable per-well volumes **or** concentration→volume planning; up to 12 stock/channels; 96/384 | Tempest CSV |
| **Bravo** | Uniform stamp (same volume, matching well IDs) | Bravo summary or per-well CSV |
| **Floi8** | 8-channel source→dest mapping; filter by contents or unique strain barcodes; uniform/gradient volumes; CSV import of source features | Floi8 transfer CSV |

Shared well IDs use **A01** style across all instruments.

## Tempest concentration mode

Per well (plate-wide defaults with optional per-well overrides):

1. **Target final volume** `V_target` (e.g. 200 µL)
2. **Base media volume** already in the well `V_base` (e.g. 100 µL)
3. **Inoculation reserve** `V_inoc` added later (e.g. 10 µL)

**Free dispense volume:**

```text
V_free = V_target − V_base − V_inoc
```

Example: `200 − 100 − 10 = 90 µL`.

Concentrations are defined **with respect to the final target volume**:

```text
V_reagent = C_target × V_target / C_stock
C_max     = C_stock × V_free / V_target
```

After planning reagents, remaining free volume is filled with a **normalizing
diluent** (configurable Tempest channel, default **12**, label “base media”):

```text
V_normalize = V_free − Σ V_reagent
```

So after Tempest + later inoculation, every well reaches `V_target`. The
normalize pad is exported as ordinary `stock_channel` rows in the Tempest CSV
(no schema change).

Pure-Python API: `plateplanner.concentration` (`plan_plate_concentrations`,
`plan_well_concentrations`, helpers). Unit-tested without Streamlit.

## CSV schemas (summary)

Full details: [`docs/csv_schemas.md`](docs/csv_schemas.md).

### Tempest

```text
plate_format,plate_id,stock_channel,well,volume_ul
```

### Bravo (summary)

```text
source_plate_format,destination_plate_format,source_plate_id,destination_plate_id,volume_ul,transfer_type
```

### Floi8 source import

```text
well,contents,strain_barcode,volume_ul
```

Sample file: [`sample_data/floi8_source_features.csv`](sample_data/floi8_source_features.csv).

### Floi8 transfer export

```text
channel,source_well,destination_well,volume_ul,contents,strain_barcode
```

## Package layout

```text
plateplanner/
  plates.py           # geometry + A01 well IDs
  models.py           # transfer plans + Floi8 selection helpers
  concentration.py    # Tempest concentration → volume planning
  exporters/          # Tempest, Bravo, Floi8 CSV
  ui/                 # Streamlit app + Plotly plate visuals
tests/                # pytest (exporters, concentration, Floi8 selection)
docs/csv_schemas.md
sample_data/
```
