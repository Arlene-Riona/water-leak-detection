# Installation

## Requirements

- Python 3.9+
- Jupyter Notebook (or JupyterLab, or VS Code's notebook support)

## Dependencies

```
pandas
numpy
openpyxl      # required to read .xlsx files
```

Install with:
```bash
pip install -r requirements.txt
```

`requirements.txt`:
```
pandas
numpy
openpyxl
```

No other external packages are required — the Mann-Kendall test, header
detection, and calendar confound logic are implemented from scratch using
only `pandas`, `numpy`, and the Python standard library (`math`, `os`).

## Getting the data in place

1. Create a `customers/` folder at the project root (this folder is
   gitignored and never committed — see `03_Data_Requirements.md`).
2. Inside it, create one subfolder per customer category
   (e.g. `Villa (Residential)/`, `Commercial/`, `Government/`,
   `Industrial (Subsidized)/`, `Hotel/`).
3. Place each customer's `.xlsx`/`.xls`/`.csv` file in the matching category
   subfolder.

## Running the pipeline

1. Open `notebooks/leak_detection.ipynb` (or `src/leak_detection.py` if
   importing programmatically).
2. Run all cells in order — cells 1 through 6 define imports and helper
   functions and must run before the crawler is invoked.
3. In the "Run the audit" cell, confirm `base_folder` points at your actual
   `customers/` directory:
   ```python
   all_audit_results = run_portfolio_leak_audit(base_folder="customers")
   ```
4. Running that cell produces `portfolio_leakage_audit_summary.csv` in the
   working directory, and prints a summary (leak count, error count, skipped
   count, MNF-not-applicable count) to the notebook output.

## Verifying the install

A quick sanity check without any real customer data:
```python
import pandas as pd, numpy as np
from leak_detection import analyze_leak_production_grade  # if using src/ as a module

rng = pd.date_range('2026-01-01', periods=24*7*12, freq='h')
base = np.where((rng.hour>=1)&(rng.hour<=4), 0.01, 0.15) + np.random.rand(len(rng))*0.02
pd.DataFrame({'Hourly': rng, 'Consumption m3': base}).to_csv('test.csv', index=False)

result = analyze_leak_production_grade('test.csv', 'Residential')
print(result['Status'], result['Leak_Suspected'])  # expect: SUCCESS NO
```