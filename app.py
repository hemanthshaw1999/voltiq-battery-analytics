from io import BytesIO
import streamlit as st
from src.ui import init, header, all_data, load_demos
from src.battery import demo_files

init(); header("VoltIQ", "Battery Test Data Analytics")
st.subheader("Transform raw battery test data into engineering insights.")
df=all_data()
if df.empty:
    st.info("No test data loaded. Generate sample battery test files to begin analysis.")
else:
    cells=df.cell_id.nunique(); tests=df.test_id.nunique(); cycles=df.cycle.nunique()
    a,b,c,d=st.columns(4)
    for col,label,value in [(a,"Tests Loaded",tests),(b,"Cells Analyzed",cells),(c,"Total Cycles",cycles),(d,"Data Points",f"{len(df):,}")]: col.metric(label,value)
    st.markdown("### Recent Analysis")
    recent=st.session_state.recent
    if recent: st.dataframe(recent,use_container_width=True,hide_index=True)
    st.markdown("### Capacity retention overview")
    import plotly.express as px
    trend=df.groupby(["cell_id","cycle"],as_index=False).capacity.max()
    if not trend.empty:
        trend["retention_pct"]=trend.groupby("cell_id").capacity.transform(lambda x:x/x.iloc[0]*100)
        st.plotly_chart(px.line(trend,x="cycle",y="retention_pct",color="cell_id",labels={"cycle":"Cycle","retention_pct":"Capacity retention (%)"}).update_layout(template="plotly_white",height=360),use_container_width=True)
st.divider()
left,right=st.columns([1,2])
with left:
    if st.button("Generate Demo Data",type="primary",use_container_width=True):
        load_demos(); st.success("Loaded three demo cells with 100 cycles each."); st.rerun()
with right:
    st.caption("Demo cells: CELL-A001, CELL-B001 and CELL-C001. Use the Upload & Validate page for your own Excel files.")
with st.expander("Download generated sample Excel files"):
    for filename, sample in demo_files():
        buffer=BytesIO()
        sample.to_excel(buffer,index=False,engine="openpyxl")
        st.download_button(f"Download {filename}",buffer.getvalue(),filename,"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",key=f"sample_{filename}")
st.markdown("### Workflow")
st.write("Upload and map cycler exports → review data quality → explore engineering curves → compare cells → export results.")
with st.expander("Analysis assumptions"):
    st.markdown("**Capacity retention** = latest cycle capacity ÷ first cycle capacity × 100.  \n**Power** = voltage × current.  \n**Energy** is integrated from power and elapsed timestamps when usable timestamps are present.  \nCoulombic efficiency is reported only where charge and discharge records can be paired by cycle; values depend on the source capacity convention.")
with st.expander("About the prototype architecture"):
    st.markdown("Excel / future CSV, cycler, lab and API sources → column mapping → validation → canonical battery data model → metrics engine → charts, comparison and exports.  \n\nThis is intentionally file-based. Future versions can add database and cloud storage, cycler/API integration, automated ingestion, and advanced analytics. It does not control equipment or predict battery life.")
