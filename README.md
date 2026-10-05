# VoltIQ — Battery Test Data Analytics Prototype

VoltIQ is a local Streamlit prototype for importing battery cycler spreadsheets, mapping and validating columns, exploring cell behavior, comparing tests, calculating metrics and exporting analysis.

## Features

- Multiple Excel workbook upload with editable source-to-canonical mapping
- Synthetic 100-cycle data for CELL-A001, CELL-B001 and CELL-C001
- Validation for missing/invalid values, duplicate timestamps, cycle gaps, voltage/temperature bounds and timestamp ordering
- Canonical Pandas schema independent of source column names
- Interactive Plotly charts with cycle filters, selection, hover, zoom, pan and image export
- Step-bounded voltage-versus-capacity curves and reference-cycle capacity retention on Battery Analysis
- Cell comparisons, capacity retention curves and observed linear trends
- Capacity, voltage, current, temperature, retention, fade, estimated coulombic efficiency and integrated net energy metrics
- CSV and multi-sheet Excel downloads, plus an HTML summary report

## Installation

Python 3.11 or newer is recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Demo Data

On Dashboard, click **Generate Demo Data** to load three slightly different cells (100 cycles each). On Upload & Validate, **Load generated demo workbooks** exercises the same alias mapping path as real cycler exports. The generated workbooks can also be created from Python using `src.battery.demo_files()` and written with Pandas `to_excel`.

## Architecture

`src/battery.py` owns ingestion normalization, aliases, validation, demo generation and metrics. `src/ui.py` contains reusable Streamlit state and chart helpers. `app.py` is the Dashboard; `pages/` contains workflow pages. The canonical schema includes timestamp, test_id, cell_id, module, cycle, step, step_type, voltage, current, capacity, specific_capacity, energy and temperature. Module, step type and specific capacity are optional source mappings.

Flow: Excel → column mapping → validation → canonical data → metrics/charts → comparison and export. The prototype is file-based; future work can add database/cloud storage and cycler or lab-system adapters without coupling metrics to Excel.

## Analysis assumptions

- Capacity retention is latest per-cycle maximum capacity divided by the first per-cycle maximum, times 100.
- Capacity fade is 100 minus retention.
- Power is voltage multiplied by current.
- Net energy is trapezoidal integration of signed power over elapsed time, converted from joules to Wh; the reported sign depends on source current convention.
- Coulombic efficiency is an estimated discharge/charge capacity endpoint ratio grouped by cycle. It is convention-dependent and is not displayed as available if charge/discharge records cannot be paired.
- Linear degradation lines describe observed values only and do not predict useful life.
- Step-bounded voltage curves use mapped step labels when available. If only current is available, positive, negative and zero current are labeled Charge, Discharge and Rest. Current direction cannot distinguish CC from CCCV.
- Capacity retention uses the maximum selected capacity value in each cycle, divided by the selected reference cycle's maximum. Cycle order follows first appearance in the source data.

## Tests

Run `python -m unittest discover -s tests -v` for focused tests covering step boundaries, label normalization, nonconsecutive cycle IDs, reference-cycle retention and invalid rows.

## Future Roadmap

1. **Phase 1:** Excel upload and analysis (this prototype)
2. **Phase 2:** Database and cloud storage
3. **Phase 3:** Battery cycler/API integration
4. **Phase 4:** Automated ingestion
5. **Phase 5:** Advanced analytics / ML

This product boundary excludes equipment control, safety decisions, inventory and manufacturing workflows.
