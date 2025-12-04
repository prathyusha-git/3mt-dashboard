import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="3MT Retention Dashboard", layout="wide")

DATA_PATH = "3MT_retention_analysis.xlsx"

@st.cache_data
def load_data(path):
    prog_year = pd.read_excel(path, sheet_name="Program-Year Participation")
    program_ret = pd.read_excel(path, sheet_name="Program Retention")
    college_ret = pd.read_excel(path, sheet_name="College Retention")
    yoy_ret = pd.read_excel(path, sheet_name="YoY Program Retention")
    return prog_year, program_ret, college_ret, yoy_ret

prog_year, program_ret, college_ret, yoy_ret = load_data(DATA_PATH)

# ---- sidebar filters ----
st.sidebar.title("🔍 Filters")

all_colleges = sorted(program_ret["College"].dropna().unique())
college_filter = st.sidebar.selectbox("College", ["All"] + all_colleges)

if college_filter != "All":
    prog_ret_filtered = program_ret[program_ret["College"] == college_filter].copy()
    prog_year_filtered = prog_year[prog_year["College"] == college_filter].copy()
else:
    prog_ret_filtered = program_ret.copy()
    prog_year_filtered = prog_year.copy()

all_programs = sorted(prog_ret_filtered["Program"].dropna().unique())
program_filter = st.sidebar.selectbox(
    "Program (optional)", ["All"] + all_programs
)

if program_filter != "All":
    prog_year_filtered = prog_year_filtered[prog_year_filtered["Program"] == program_filter]

st.title("🎓 3MT Retention Analysis — Multi-Tab Dashboard")

# ============================================================================
# Helper computations
# ============================================================================

def college_program_retention_stats(program_ret_df):
    """Aggregate program retention by college (avg, median, pct full, etc.)."""
    stats = (
        program_ret_df
        .dropna(subset=["retention_rate"])
        .groupby("College")
        .agg(
            num_programs=("Program", "nunique"),
            avg_retention=("retention_rate", "mean"),
            median_retention=("retention_rate", "median"),
            pct_full_retention=("retention_rate", lambda s: (s == 1).mean()),
            max_streak=("longest_streak", "max"),
        )
        .reset_index()
    )
    stats["pct_full_retention"] = (stats["pct_full_retention"] * 100).round(1)
    stats["avg_retention"] = stats["avg_retention"].round(3)
    stats["median_retention"] = stats["median_retention"].round(3)
    return stats

def build_cohort_table(prog_year_df, program_ret_df):
    """Cohort = first_year of each program; track survival over years."""
    base = program_ret_df[["College", "Program", "first_year"]].dropna()
    base = base.rename(columns={"first_year": "cohort"})
    merged = prog_year_df.merge(base, on=["College", "Program"], how="inner")
    merged = merged[merged["Participated"] == 1]

    rows = []
    for cohort, sub in merged.groupby("cohort"):
        try:
            cohort = int(cohort)
        except Exception:
            continue
        cohort_programs = sub[["College", "Program"]].drop_duplicates()
        total_programs = len(cohort_programs)
        for year in sorted(sub["Year"].unique()):
            active = (
                sub[sub["Year"] == year][["College", "Program"]]
                .drop_duplicates()
            )
            active_n = len(active)
            rate = active_n / total_programs if total_programs > 0 else 0
            rows.append(
                {
                    "cohort": cohort,
                    "year": int(year),
                    "total_programs": total_programs,
                    "active_programs": active_n,
                    "retention_rate": round(rate, 3),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["cohort", "year", "total_programs",
                                     "active_programs", "retention_rate"])
    return pd.DataFrame(rows)

def build_new_entry_table(program_ret_df, prog_year_df):
    """New programs entering each year and share among active programs."""
    entry = (
        program_ret_df.dropna(subset=["first_year"])
        .groupby("first_year")
        .size()
        .reset_index(name="new_programs")
        .rename(columns={"first_year": "Year"})
    )
    active = (
        prog_year_df[prog_year_df["Participated"] == 1]
        .groupby("Year")["Program"]
        .nunique()
        .reset_index(name="active_programs")
    )
    merged = entry.merge(active, on="Year", how="left")
    merged["entry_rate"] = (merged["new_programs"] / merged["active_programs"]).round(3)
    return merged

def build_dropout_table(program_ret_df):
    """Programs that stop participating after a year (last_year)."""
    last = program_ret_df.dropna(subset=["last_year"]).copy()
    last["last_year"] = last["last_year"].astype(int)
    drop = (
        last.groupby("last_year")
        .size()
        .reset_index(name="programs_dropped")
    )
    by_college = (
        last.groupby(["last_year", "College"])
        .size()
        .reset_index(name="programs_dropped")
    )
    return drop, by_college

college_stats = college_program_retention_stats(program_ret)
cohort_df = build_cohort_table(prog_year, program_ret)
entry_df = build_new_entry_table(program_ret, prog_year)
drop_df, drop_by_college_df = build_dropout_table(program_ret)

# ============================================================================
# Tabs
# ============================================================================

(
    tab_overview,
    tab_program,
    tab_college,
    tab_heatmap,
    tab_cohort,
    tab_entry,
    tab_dropout,
    tab_yoy,
    tab_data,
) = st.tabs([
    "📊 Overview",
    "📘 Program Retention",
    "🏫 College Retention",
    "🔥 Streak Heatmap",
    "👥 Cohort Survival",
    "🆕 New Program Entry",
    "📉 Drop-Off Analysis",
    "🔄 YoY Retention",
    "📂 Raw Data",
])

# ------------------------------- OVERVIEW -----------------------------------
with tab_overview:
    st.subheader("High-Level Snapshot")

    c1, c2, c3 = st.columns(3)
    total_programs = program_ret["Program"].nunique()
    total_colleges = program_ret["College"].nunique()
    years_span = f"{int(prog_year['Year'].min())}–{int(prog_year['Year'].max())}"

    with c1:
        st.metric("Total Programs", total_programs)
    with c2:
        st.metric("Total Colleges", total_colleges)
    with c3:
        st.metric("Years Covered", years_span)

    st.markdown("### Average Program Retention by College")
    fig_col_stats = px.bar(
        college_stats,
        x="College",
        y="avg_retention",
        text="avg_retention",
        color="avg_retention",
        title="Average Program Retention Rate (per College)",
    )
    st.plotly_chart(fig_col_stats, use_container_width=True)

    st.markdown("### YoY Program Retention")
    fig_yoy = px.line(
        yoy_ret,
        x="from_year",
        y="retention_rate",
        markers=True,
        title="Year-over-Year Program Retention Rate",
    )
    st.plotly_chart(fig_yoy, use_container_width=True)

# ------------------------------ PROGRAM TAB ---------------------------------
with tab_program:
    st.subheader("Program-Level Retention")

    st.write(f"Filtered by College: **{college_filter}**, Program: **{program_filter}**")
    st.dataframe(prog_ret_filtered)

    fig_prog = px.bar(
        prog_ret_filtered.sort_values("retention_rate", ascending=False),
        x="Program",
        y="retention_rate",
        color="retention_rate",
        text="retention_rate",
        title="Program Retention Rates",
    )
    st.plotly_chart(fig_prog, use_container_width=True)

# ------------------------------ COLLEGE TAB ---------------------------------
with tab_college:
    st.subheader("College-Level Retention & Program Stats")

    st.dataframe(college_stats)

    col1, col2 = st.columns(2)
    with col1:
        fig_c_ret = px.bar(
            college_ret,
            x="College",
            y="retention_rate",
            text="retention_rate",
            color="retention_rate",
            title="College Participation Retention (Any Program Present)",
        )
        st.plotly_chart(fig_c_ret, use_container_width=True)

    with col2:
        fig_c_prog = px.bar(
            college_stats,
            x="College",
            y="pct_full_retention",
            text="pct_full_retention",
            title="% of Programs with 100% Retention (within college)",
        )
        st.plotly_chart(fig_c_prog, use_container_width=True)

# ------------------------------ HEATMAP TAB ---------------------------------
with tab_heatmap:
    st.subheader("Program Participation Streak Heatmap")

    pivot = prog_year_filtered.pivot_table(
        index="Program",
        columns="Year",
        values="Participated",
        aggfunc="max",
        fill_value=0,
    )
    if pivot.empty:
        st.info("No data for the current filter selection.")
    else:
        fig_heat = px.imshow(
            pivot,
            aspect="auto",
            color_continuous_scale="Viridis",
            labels={"color": "Participated (0/1)"},
            title="Program Participation by Year (1 = Present)",
        )
        st.plotly_chart(fig_heat, use_container_width=True)

# ------------------------------ COHORT TAB ----------------------------------
with tab_cohort:
    st.subheader("Cohort-Based Retention (Programs grouped by first active year)")

    if cohort_df.empty:
        st.info("No cohort data available.")
    else:
        selected_cohort = st.selectbox(
            "Select Cohort (first participation year):",
            sorted(cohort_df["cohort"].unique()),
        )
        sub = cohort_df[cohort_df["cohort"] == selected_cohort]

        c1, c2 = st.columns(2)
        with c1:
            fig_cohort = px.line(
                sub,
                x="year",
                y="retention_rate",
                markers=True,
                title=f"Cohort {selected_cohort}: Retention Over Time",
            )
            st.plotly_chart(fig_cohort, use_container_width=True)
        with c2:
            st.dataframe(sub)

        st.markdown("### All Cohort Summary")
        st.dataframe(cohort_df)

# ------------------------------ ENTRY TAB -----------------------------------
with tab_entry:
    st.subheader("New Program Entry per Year")

    if entry_df.empty:
        st.info("No entry data available.")
    else:
        c1, c2 = st.columns(2)
        with c1:
            fig_new = px.bar(
                entry_df,
                x="Year",
                y="new_programs",
                title="Number of New Programs Entering 3MT Each Year",
                text="new_programs",
            )
            st.plotly_chart(fig_new, use_container_width=True)

        with c2:
            fig_rate = px.line(
                entry_df,
                x="Year",
                y="entry_rate",
                markers=True,
                title="New Program Entry Rate (New / Active Programs)",
            )
            st.plotly_chart(fig_rate, use_container_width=True)

        st.dataframe(entry_df)

# ----------------------------- DROPOUT TAB ----------------------------------
with tab_dropout:
    st.subheader("Program Drop-Off Analysis (Last Active Year)")

    if drop_df.empty:
        st.info("No drop-off data available.")
    else:
        fig_drop = px.bar(
            drop_df,
            x="last_year",
            y="programs_dropped",
            title="Programs Dropping Out by Last Active Year",
            text="programs_dropped",
        )
        st.plotly_chart(fig_drop, use_container_width=True)

        st.markdown("### Drop-Off by College & Year")
        st.dataframe(drop_by_college_df)

# ------------------------------- YOY TAB ------------------------------------
with tab_yoy:
    st.subheader("Year-over-Year Program Retention")

    fig_yoy2 = px.line(
        yoy_ret,
        x="from_year",
        y="retention_rate",
        markers=True,
        title="YoY Retention Rate (Programs Returning Next Year)",
    )
    st.plotly_chart(fig_yoy2, use_container_width=True)

    st.dataframe(yoy_ret)

# ------------------------------- DATA TAB -----------------------------------
with tab_data:
    st.subheader("Raw Tables")

    st.markdown("**Program-Year Participation**")
    st.dataframe(prog_year)

    st.markdown("**Program Retention**")
    st.dataframe(program_ret)

    st.markdown("**College Retention**")
    st.dataframe(college_ret)
