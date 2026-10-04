import streamlit as st
import pandas as pd
from src.ui import init,header,all_data
from src.battery import calculate_metrics,energy_from_power
init(); header("Battery Metrics","Cycle-level capacity, electrical and thermal summary metrics.")
df=all_data()
if df.empty: st.info("Load demo data on Dashboard or upload a workbook first."); st.stop()
metrics=calculate_metrics(df)
st.dataframe(metrics,use_container_width=True,hide_index=True)
st.caption("Energy integration uses signed power over elapsed time; charge/discharge conventions and capacity definitions vary by cycler.")
st.subheader("Per-test energy from power integration")
energy=[]
for (test,cell),g in df.groupby(["test_id","cell_id"]): energy.append({"Test":test,"Cell":cell,"Integrated net energy (Wh)":energy_from_power(g)})
st.dataframe(pd.DataFrame(energy),use_container_width=True,hide_index=True)
with st.expander("Definitions and limitations"):
    st.markdown("- Capacity retention = latest cycle maximum capacity / first cycle maximum capacity × 100.  \n- Capacity fade = 100 − retention.  \n- Coulombic efficiency is estimated from the ratio of discharge to charge capacity endpoints grouped by cycle and is dataset-convention dependent.  \n- Power = voltage × current.  \n- Integrated energy is unavailable when timestamps are unusable.  \n- No metric is a safety determination or battery-life prediction.")
