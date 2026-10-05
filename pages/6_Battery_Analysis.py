import plotly.express as px
import streamlit as st

from src.battery import (
    apply_step_type_mapping,
    available_step_types,
    capacity_retention_by_cycle,
    prepare_voltage_capacity_data,
)
from src.ui import all_data, header, init


init()
header("Battery Analysis", "Step-aware voltage and cycle-retention views.")
data = all_data()
if data.empty:
    st.info("Load a workbook on Upload & Validate or generate demo data on the Dashboard first.")
    st.stop()

# Keep each test and cell separate so reused cycle IDs from different files do
# not get combined into a single curve.
identity_columns = [column for column in ["test_id", "cell_id"] if column in data]
identities = data[identity_columns].drop_duplicates().itertuples(index=False, name=None)
identities = list(identities)
if identities:
    chosen_identity = st.selectbox(
        "Test and cell",
        identities,
        format_func=lambda item: " · ".join(str(value) for value in item),
    )
    selected = data
    for column, value in zip(identity_columns, chosen_identity):
        selected = selected[selected[column] == value]
else:
    selected = data

chosen_module = None
if "module" in selected and selected.module.notna().any():
    modules = selected.module.dropna().drop_duplicates().tolist()
    chosen_module = st.selectbox("Module / program", modules)
    selected = selected[selected.module == chosen_module]
else:
    st.caption("No module or program column was detected in this file.")

if "step" in selected and selected.step.notna().any():
    step_ids = selected.loc[selected.step.notna(), "step"].drop_duplicates().tolist()
    source_has_step_types = (
        "step_type" in selected
        and selected.step_type.notna().any()
        and selected.step_type.astype(str).str.strip().ne("").any()
    )
    step_type_options = [
        "Auto (source label / current direction)",
        "Rest",
        "CC Charge",
        "CCCV Charge",
        "CC Discharge",
        "CCCV Discharge",
        "Charge",
        "Discharge",
        "Other",
    ]
    step_scope = "_".join(str(value) for value in chosen_identity) if identities else "all"
    if chosen_module is not None:
        step_scope += f"_{chosen_module}"
    overrides = {}
    with st.expander("Map Step IDs to Step Types (optional)", expanded=not source_has_step_types):
        st.caption(
            "Use this when the workbook has numeric Step IDs but no step-type labels. "
            "Auto uses source labels or current direction; current direction cannot distinguish CC from CCCV."
        )
        for step_id in step_ids:
            choice = st.selectbox(
                f"Step {step_id}",
                step_type_options,
                key=f"step_type_map_{step_scope}_{step_id!r}",
            )
            if choice != step_type_options[0]:
                overrides[step_id] = choice
    selected = apply_step_type_mapping(selected, overrides)

capacity_options = [
    column for column in ["specific_capacity", "capacity"]
    if column in selected and selected[column].notna().any()
]
if not capacity_options:
    st.error("Map a Capacity or Specific Capacity column on Upload & Validate to continue.")
    st.stop()
capacity_column = st.selectbox(
    "Capacity column",
    capacity_options,
    format_func=lambda field: "Specific Capacity" if field == "specific_capacity" else "Capacity",
    index=0,
)
if capacity_column == "capacity" and "specific_capacity" not in capacity_options:
    st.info("No specific-capacity column is present. The voltage plot will use the mapped Capacity column as provided.")

st.subheader("Voltage vs Capacity by Step")
has_step_id = "step" in selected and selected.step.notna().any()
has_step_type = "step_type" in selected and selected.step_type.notna().any()
if not has_step_id and not has_step_type:
    st.warning("No Step or Step Index column was mapped. Map it on Upload & Validate to create step-bounded curves.")
else:
    cycle_options = selected.cycle.dropna().drop_duplicates().tolist()
    if not cycle_options:
        st.warning("No valid cycle identifiers were found.")
    else:
        cycle_choices = st.multiselect("Cycle(s)", cycle_options, default=[cycle_options[-1]])
        type_options = available_step_types(selected)
        default_types = [name for name in type_options if name not in {"Rest", "Unknown"}]
        step_choices = st.multiselect("Step type(s)", type_options, default=default_types)
        if not step_choices:
            st.info("Select at least one step type to draw the voltage curve.")
        else:
            voltage_data, skipped = prepare_voltage_capacity_data(
                selected,
                cycles=cycle_choices,
                step_types=step_choices,
                capacity_column=capacity_column,
            )
            if skipped:
                st.warning(
                    f"{skipped:,} rows were skipped because cycle, step, voltage, or the selected capacity value was missing or invalid."
                )
            if voltage_data.empty:
                st.info("No valid rows match the selected cycles and step types.")
            else:
                label = "Specific Capacity" if capacity_column == "specific_capacity" else "Capacity"
                hover = [column for column in ["cycle", "step", "step_type", "module", "cell_id"] if column in voltage_data]
                fig = px.line(
                    voltage_data,
                    x=capacity_column,
                    y="voltage",
                    color="step_type",
                    line_dash="cycle" if len(cycle_choices) > 1 else None,
                    line_group="step_block",
                    hover_data=hover,
                    labels={capacity_column: label, "voltage": "Voltage (V)", "step_type": "Step type"},
                )
                fig.update_layout(template="plotly_white", height=440, legend_title="Step type")
                st.plotly_chart(fig, use_container_width=True)
        if not any(name.startswith("CC") for name in type_options):
            st.caption(
                "This file has step numbers but no explicit CC/CCCV step labels. Charge and discharge are inferred from current direction, so those modes cannot be distinguished here."
            )

st.subheader("Cycle vs Capacity Retention")
cycle_options = selected.cycle.dropna().drop_duplicates().tolist()
if not cycle_options:
    st.warning("No valid cycle identifiers are available for capacity retention.")
else:
    reference_cycle = st.selectbox("Reference cycle", cycle_options, index=0)
    retention, skipped = capacity_retention_by_cycle(
        selected,
        reference_cycle=reference_cycle,
        capacity_column=capacity_column,
    )
    if skipped:
        st.warning(f"{skipped:,} rows were skipped because the cycle ID or selected capacity value was missing or invalid.")
    if retention.empty:
        st.warning("The selected reference cycle has no valid capacity measurement.")
    elif not retention.retention_pct.notna().any():
        st.warning("Capacity retention is unavailable because reference-cycle capacity is zero or invalid.")
    else:
        fig = px.line(
            retention,
            x="cycle",
            y="retention_pct",
            markers=True,
            labels={"cycle": "Cycle Number", "retention_pct": "Capacity Retention (%)"},
        )
        fig.update_layout(template="plotly_white", height=390, yaxis_title="Capacity Retention (%)")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Capacity retention = cycle capacity ÷ capacity at reference cycle {reference_cycle} × 100.")
