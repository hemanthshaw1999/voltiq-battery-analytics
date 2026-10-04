import streamlit as st
import pandas as pd
import plotly.express as px
from src.ui import init,header,all_data,excel_bytes
from src.battery import calculate_metrics,validate_frame
init(); header("Export & Report","Download normalized data, metrics and a concise engineering report.")
df=all_data()
if df.empty: st.info("Load data before exporting."); st.stop()
metrics=calculate_metrics(df)
validation=pd.DataFrame([{"file":name,**validate_frame(data)} for name,data in st.session_state.datasets.items()])
summary=metrics[["test_id","cell_id","cycles","capacity_retention_pct","average_voltage","max_temperature"]]
a,b=st.columns(2)
a.download_button("Download cleaned data CSV",df.to_csv(index=False),"voltiq_cleaned_data.csv","text/csv",use_container_width=True)
b.download_button("Download metrics CSV",metrics.to_csv(index=False),"voltiq_metrics.csv","text/csv",use_container_width=True)
book=excel_bytes({"Summary":summary,"Metrics":metrics,"Cleaned Data":df,"Validation Results":validation})
st.download_button("Download Excel workbook",book,"voltiq_analysis.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",type="primary")
st.subheader("Summary report")
st.dataframe(summary,use_container_width=True,hide_index=True)
warnings=[w for name,data in st.session_state.datasets.items() for w in validate_frame(data)["warnings"]]
trend=df.groupby(["cell_id","cycle"],as_index=False).capacity.max()
trend["retention_pct"]=trend.groupby("cell_id").capacity.transform(lambda s:s/s.iloc[0]*100)
charts=[]
for fig in [
    px.line(trend,x="cycle",y="capacity",color="cell_id",title="Capacity vs Cycle"),
    px.line(df,x="capacity",y="voltage",color="cell_id",title="Voltage vs Capacity"),
    px.line(df.groupby(["cell_id","cycle"],as_index=False).temperature.mean(),x="cycle",y="temperature",color="cell_id",title="Temperature vs Cycle"),
]:
    fig.update_layout(template="plotly_white",height=360)
    charts.append(fig.to_html(full_html=False,include_plotlyjs="cdn" if not charts else False))
report=f"""<!doctype html><html><head><meta charset='utf-8'><title>VoltIQ Battery Test Report</title><style>body{{font:15px Arial;max-width:1000px;margin:40px auto;color:#193040}}h1{{color:#145768}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #dce5eb;padding:8px;text-align:left}}th{{background:#edf4f6}}</style></head><body><h1>VoltIQ Battery Test Report</h1><p>Generated {pd.Timestamp.now():%Y-%m-%d %H:%M} · {len(df):,} data points · {df.cycle.nunique()} cycles</p><h2>Key Metrics</h2>{summary.to_html(index=False,na_rep='Not available')}<h2>Engineering Charts</h2>{''.join(charts)}<h2>Data Quality</h2><p>{'No warnings.' if not warnings else '<br>'.join(warnings)}</p><p>Observed data summary only; not a lifetime prediction or safety assessment.</p></body></html>"""
st.download_button("Download HTML report",report,"voltiq_battery_test_report.html","text/html")
st.caption("For charts, use the interactive visualization and comparison pages, where Plotly toolbar export is available.")
