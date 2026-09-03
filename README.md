# PlatePlanner

Laboratory **liquid-transfer planner** for **Tempest**, **Bravo**, and **Floi8**.
Plan volume transfers on interactive plate schematics and export instrument CSVs.

> **MVP scope:** volume transfers only. Concentration → volume calculation is a
> stub/TODO in `plateplanner/concentration.py`.

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
each page.

## Run tests

```bash
pytest
```

## Instruments

| Instrument | What it plans | Export |
|------------|---------------|--------|
| **Tempest** | Variable per-well volumes; up to 12 stock/channels; 96/384 | Tempest CSV |
| **Bravo** | Uniform stamp (same volume, matching well IDs) | Bravo summary or per-well CSV |
| **Floi8** | 8-channel source→dest mapping; filter by contents or unique strain barcodes; uniform/gradient volumes; CSV import of source features | Floi8 transfer CSV |

Shared well IDs use **A01** style across all instruments.

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
  concentration.py    # STUB / TODO — not implemented
  exporters/          # Tempest, Bravo, Floi8 CSV
  ui/                 # Streamlit app + Plotly plate visuals
tests/                # pytest (exporters + Floi8 selection)
docs/csv_schemas.md
sample_data/
```

## Concentration (TODO)

Do not use concentration mode yet. Calling
`plateplanner.concentration.volume_from_concentration` raises
`ConcentrationNotImplementedError`. Planned: dilution math (C₁V₁ = C₂V₂) wired
into Tempest/Floi8 planners later.
