import streamlit as st
import pandas as pd
from src.ui import init,header,store_upload,all_data
from src.battery import CANONICAL,validate_frame,demo_files
init(); header("Upload & Validate","Map cycler exports into VoltIQ's canonical battery schema.")
uploads=st.file_uploader("Upload battery test workbooks (.xlsx)",type=["xlsx"],accept_multiple_files=True)
if st.button("Load generated demo workbooks"):
    for name,raw in demo_files():
        from src.battery import detect_mapping,normalize_frame
        df=normalize_frame(raw,detect_mapping(raw.columns,raw),name); st.session_state.datasets[name]=df
        st.session_state.recent.insert(0,{"file":name,"rows":len(df),"status":validate_frame(df)["status"]})
    st.rerun()
if uploads:
    for upload in uploads:
        with st.expander(upload.name,expanded=True):
            try:
                raw=pd.read_excel(upload); st.caption(f"{len(raw):,} rows · {len(raw.columns)} source columns")
                detected=__import__('src.battery',fromlist=['detect_mapping']).detect_mapping(raw.columns,raw)
                st.write("Detected mapping")
                mapping={}
                cols=list(raw.columns)
                for field in CANONICAL:
                    idx=cols.index(detected[field]) if field in detected and detected[field] in cols else 0
                    selected=st.selectbox(field.replace('_',' ').title(),["— Not mapped —"]+cols,index=(idx+1 if field in detected else 0),key=f"{upload.name}_{field}")
                    if selected!="— Not mapped —": mapping[field]=selected
                if st.button("Validate and load",key=f"load_{upload.name}"):
                    raw2,m,df,result,error=store_upload(upload,mapping)
                    if error: st.error(f"Unable to process file. {error}")
                    else:
                        st.success(f"{result['status']} · {len(df):,} records normalized")
                        for msg in result['errors']+result['warnings']: st.warning(msg)
                        st.dataframe(df.head(8),use_container_width=True)
            except Exception as exc: st.error(f"Unable to read this workbook: {exc}")
df=all_data()
if not df.empty:
    st.subheader("Loaded files")
    rows=[]
    for name,data in st.session_state.datasets.items():
        q=validate_frame(data); rows.append({"File":name,"Rows":len(data),"Columns":len(data.columns),"Detected Cell":", ".join(data.cell_id.dropna().unique()[:3]),"Detected Test":", ".join(data.test_id.dropna().unique()[:3]),"Status":q['status']})
    st.dataframe(rows,use_container_width=True,hide_index=True)
    st.caption("Raw source values are retained only in the source file; normalization and validation do not silently repair records.")
