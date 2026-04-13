# Cohort Retention Engine

Self-serve cohort analytics tool. Upload any event CSV and get a full retention matrix, drop-off heatmap, and average retention curve — no SQL required.

**Built from:** the manual cohort analysis process used at JMT Worldwide on a 50K+ MAU database.

## Stack
- Python · pandas · Plotly · Streamlit

## Usage

```bash
pip install -r requirements.txt
streamlit run app.py
```

## CSV Format

```
user_id, event_date, event_type
u_001, 2023-01-15, acquisition
u_001, 2023-02-03, active
```

`event_type` is optional. The engine determines cohorts from each user's earliest `event_date`.

## Features
- Monthly or weekly cohort grouping
- Retention matrix (absolute + percentage)
- Period-over-period drop-off heatmap — surfaces where churn accelerates
- Average retention curve with per-cohort overlays
- Cohort summary table with CSV export
- Built-in sample data generator
