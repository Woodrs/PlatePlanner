# PlatePlanner CSV schemas

All volumes are in **microliters (µL)**. Well IDs use the shared **A01** style
(row letter + zero-padded column).

Concentration-based volume calculation is **not** implemented in the MVP; see
`plateplanner/concentration.py`.

---

## Tempest

Variable per-well volumes from up to 12 stock solutions / channels.

### Export columns

| Column | Type | Description |
|--------|------|-------------|
| `plate_format` | `96` \| `384` | Destination plate format |
| `plate_id` | string | Destination plate identifier |
| `stock_channel` | int 1–12 | Stock / dispense channel |
| `well` | A01-style | Destination well |
| `volume_ul` | float | Volume dispensed (µL) |

One row per (well × stock_channel) with volume &gt; 0. Rows are ordered by
`stock_channel`, then `well`.

### Example

```csv
plate_format,plate_id,stock_channel,well,volume_ul
96,DEST_001,1,A01,5
96,DEST_001,1,A02,7.5
96,DEST_001,2,A01,10
```

---

## Bravo

Uniform stamp: the same volume from every source well to the matching
destination well ID.

### Summary export (default)

| Column | Type | Description |
|--------|------|-------------|
| `source_plate_format` | `96` \| `384` | Source plate format |
| `destination_plate_format` | `96` \| `384` | Destination plate format |
| `source_plate_id` | string | Source plate ID |
| `destination_plate_id` | string | Destination plate ID |
| `volume_ul` | float | Stamp volume (µL) |
| `transfer_type` | `uniform_stamp` | Constant |

### Per-well export

Same as summary, plus `source_well` and `destination_well` (identical IDs for a
classic stamp). Only wells present on **both** plates are emitted.

### Example (summary)

```csv
source_plate_format,destination_plate_format,source_plate_id,destination_plate_id,volume_ul,transfer_type
96,96,BRAVO_SRC,BRAVO_DST,25,uniform_stamp
```

---

## Floi8

Eight independent channels with arbitrary source→destination well mapping.

### Source features import

| Column | Required | Aliases | Description |
|--------|----------|---------|-------------|
| `well` | yes | `well_id`, `source_well` | Source well |
| `contents` | no | `content`, `reagent` | Contents / media label |
| `strain_barcode` | no | `barcode`, `strain` | Strain barcode |
| `volume_ul` | no | `volume`, `vol_ul` | Optional source volume annotation |

### Transfer export

| Column | Type | Description |
|--------|------|-------------|
| `channel` | int 1–8 or empty | Assigned Floi8 channel |
| `source_well` | A01-style | Source well |
| `destination_well` | A01-style | Destination well |
| `volume_ul` | float | Transfer volume (µL) |
| `contents` | string | Copied from source feature when known |
| `strain_barcode` | string | Copied from source feature when known |

### Selection rules

- **By contents**: exact match (case-insensitive by default).
- **By unique strain barcodes**: only barcodes that appear **exactly once** on
  the source feature list are eligible when `unique_only=True` (default).

### Example transfer export

```csv
channel,source_well,destination_well,volume_ul,contents,strain_barcode
1,A01,A01,10,LB Media,STR001
2,A02,A02,12.5,LB Media,STR002
```
