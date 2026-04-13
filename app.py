"""
Cohort Retention Engine — Streamlit App
Upload event CSVs, get retention matrices, curves, and drop-off analysis instantly.
"""

import io
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from cohort_engine import (
    load_and_validate,
    build_cohort_matrix,
    build_retention_pct,
    compute_dropoff,
    avg_retention_curve,
    cohort_summary,
    generate_sample_data,
)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Cohort Retention Engine",
    page_icon="📊",
    layout="wide",
)

st.title("📊 Cohort Retention Engine")
st.caption(
    "Upload event data → get retention matrices, drop-off analysis, and cohort curves. "
    "Built to generalize the manual SQL cohort analysis process."
)

# ── Sidebar controls ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("Configuration")

    uploaded = st.file_uploader(
        "Upload event CSV",
        type=["csv"],
        help="Required columns: user_id, event_date. Optional: event_type",
    )

    period = st.selectbox("Cohort period", ["Monthly", "Weekly"], index=0)
    period_code = "M" if period == "Monthly" else "W"

    st.divider()
    st.subheader("Expected CSV format")
    st.code("user_id, event_date, event_type\nu_001, 2023-01-15, acquisition\nu_001, 2023-02-03, active", language="text")

    use_sample = st.button("Load sample data instead")

# ── Data loading ─────────────────────────────────────────────────────────────
df_raw = None

if use_sample:
    df_raw = generate_sample_data()
    st.info("Using synthetic sample data (400 users, 8 months, natural churn curve).")
elif uploaded:
    try:
        df_raw = pd.read_csv(uploaded)
    except Exception as e:
        st.error(f"Could not read file: {e}")

if df_raw is None:
    st.markdown(
        """
        ### How it works
        1. **Upload** any event CSV with `user_id` and `event_date` columns.
        2. The engine determines each user's **acquisition cohort** from their first event.
        3. It calculates **how many users from each cohort remained active** in subsequent periods.
        4. You get a **retention matrix**, **drop-off heatmap**, and **average retention curve** — instantly.

        Hit **Load sample data** in the sidebar to see a live example.
        """
    )
    st.stop()

# ── Processing ───────────────────────────────────────────────────────────────
try:
    df = load_and_validate(df_raw)
except ValueError as e:
    st.error(str(e))
    st.stop()

matrix = build_cohort_matrix(df, period=period_code)
pct = build_retention_pct(matrix)
dropoff = compute_dropoff(pct)
curve = avg_retention_curve(pct)
summary = cohort_summary(matrix, pct)

# ── Top metrics ──────────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Users", f"{df['user_id'].nunique():,}")
col2.metric("Cohorts", len(matrix))
col3.metric("Periods Tracked", len(matrix.columns))
p1_avg = pct.iloc[:, 1].mean() if len(pct.columns) > 1 else 0
col4.metric("Avg Period-1 Retention", f"{p1_avg:.1f}%")

st.divider()

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(
    ["Retention Matrix", "Drop-off Heatmap", "Average Retention Curve", "Cohort Summary"]
)

# Tab 1 — Retention Matrix
with tab1:
    st.subheader("Retention Matrix (%)")
    st.caption("Percentage of each cohort still active at each period after acquisition.")

    fig = go.Figure(
        data=go.Heatmap(
            z=pct.values,
            x=pct.columns.tolist(),
            y=pct.index.tolist(),
            colorscale=[
                [0.0, "#fee8d6"], [0.3, "#f4956e"],
                [0.6, "#2d7dd2"], [1.0, "#0a3d6b"],
            ],
            text=pct.values,
            texttemplate="%{text:.1f}%",
            textfont={"size": 12},
            hoverongaps=False,
            zmin=0, zmax=100,
        )
    )
    fig.update_layout(
        height=max(300, len(pct) * 45 + 80),
        xaxis_title="Period Index",
        yaxis_title="Cohort",
        margin=dict(l=20, r=20, t=20, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Show raw counts"):
        st.dataframe(matrix.fillna("—"), use_container_width=True)

# Tab 2 — Drop-off Heatmap
with tab2:
    st.subheader("Period-over-Period Drop-off (%)")
    st.caption("Negative values = users lost. Larger drops highlight where churn accelerates.")

    fig2 = go.Figure(
        data=go.Heatmap(
            z=dropoff.values,
            x=dropoff.columns.tolist(),
            y=dropoff.index.tolist(),
            colorscale="RdYlGn",
            text=dropoff.values,
            texttemplate="%{text:.1f}%",
            textfont={"size": 11},
            zmid=0,
        )
    )
    fig2.update_layout(
        height=max(300, len(dropoff) * 45 + 80),
        xaxis_title="Period Transition",
        yaxis_title="Cohort",
        margin=dict(l=20, r=20, t=20, b=40),
    )
    st.plotly_chart(fig2, use_container_width=True)

    worst_transition = dropoff.mean(axis=0).idxmin()
    worst_val = dropoff.mean(axis=0).min()
    st.info(f"**Steepest average drop-off:** {worst_transition} ({worst_val:+.1f}%)")

# Tab 3 — Retention Curve
with tab3:
    st.subheader("Average Retention Curve")
    st.caption("Mean retention across all cohorts at each period. Shows your typical user lifecycle.")

    fig3 = go.Figure()
    fig3.add_trace(go.Scatter(
        x=curve.index.tolist(),
        y=curve.values,
        mode="lines+markers",
        line=dict(color="#2d7dd2", width=3),
        marker=dict(size=8),
        name="Avg Retention",
        fill="tozeroy",
        fillcolor="rgba(45,125,210,0.12)",
    ))

    # Individual cohort lines
    for cohort in pct.index:
        fig3.add_trace(go.Scatter(
            x=pct.columns.tolist(),
            y=pct.loc[cohort].values,
            mode="lines",
            line=dict(width=1, dash="dot", color="rgba(150,150,150,0.4)"),
            name=str(cohort),
            showlegend=False,
        ))

    fig3.update_layout(
        height=380,
        xaxis_title="Period Index",
        yaxis_title="Retention (%)",
        yaxis=dict(range=[0, 105]),
        margin=dict(l=20, r=20, t=20, b=40),
    )
    st.plotly_chart(fig3, use_container_width=True)

# Tab 4 — Summary
with tab4:
    st.subheader("Cohort Summary")
    st.dataframe(
        summary.style.format(
            {c: "{:.1f}%" for c in summary.columns if "%" in c}
        ).background_gradient(
            cmap="Blues",
            subset=[c for c in summary.columns if "%" in c],
        ),
        use_container_width=True,
    )

    buf = io.StringIO()
    summary.to_csv(buf)
    st.download_button(
        "Download summary CSV",
        data=buf.getvalue(),
        file_name="cohort_summary.csv",
        mime="text/csv",
    )
