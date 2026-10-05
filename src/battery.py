"""Canonical battery data ingestion, validation, demo generation and metrics."""
from __future__ import annotations

from io import BytesIO
import re
import numpy as np
import pandas as pd

CANONICAL = ["timestamp", "test_id", "cell_id", "module", "cycle", "step", "step_type", "voltage", "current", "capacity", "specific_capacity", "energy", "temperature"]
ALIASES = {
    "timestamp": ["time", "datetime", "date/time", "date_time", "timestamp"],
    "cycle": ["cycle", "cycle number", "cycle_number", "cycleindex", "cycle index"],
    "step": ["step", "step number", "step_index", "step index", "step no", "step number"],
    "step_type": ["step type", "step_type", "step description", "step mode", "operation type"],
    "module": ["module", "module id", "module_id", "program", "program name", "program id", "block"],
    "voltage": ["voltage", "voltage(v)", "voltage_v", "v"],
    "current": ["current", "current(a)", "current_a", "i"],
    "capacity": ["capacity", "capacity(ah)", "capacity_ah", "discharge capacity", "discharge capacity(ah)"],
    "specific_capacity": ["specific capacity", "specific_capacity", "specific capacity (ah/kg)", "specific capacity (mah/g)", "specific capacity(ah/kg)", "specific capacity(mah/g)"],
    "energy": ["energy", "energy(wh)", "energy_wh"],
    "temperature": ["temperature", "temp", "temp(c)", "temperature_c", "temperature(c)"],
    "cell_id": ["cell_id", "cell id", "cell", "sample"],
    "test_id": ["test_id", "test id", "test", "experiment"],
}
REQUIRED = ["cycle", "voltage"]

def _key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())

def detect_mapping(columns, frame=None):
    result = {}
    for col in columns:
        key = _key(col)
        if key == "step" and frame is not None and col in frame:
            values = frame[col].dropna()
            if len(values) and pd.to_numeric(values, errors="coerce").notna().sum() != len(values):
                result.setdefault("step_type", col)
                continue
        for field, aliases in ALIASES.items():
            if key in aliases or key.replace(" ", "") in [a.replace(" ", "") for a in aliases]:
                if field not in result:
                    result[field] = col
    return result

def normalize_frame(frame: pd.DataFrame, mapping: dict, filename="upload") -> pd.DataFrame:
    missing = [f for f in REQUIRED if not mapping.get(f) or mapping[f] not in frame.columns]
    if not any(mapping.get(field) in frame.columns for field in ["capacity", "specific_capacity"]):
        missing.append("capacity or specific_capacity")
    if missing:
        raise ValueError(f"Required field(s) could not be mapped: {', '.join(missing)}. Available columns: {', '.join(map(str, frame.columns))}")
    out = pd.DataFrame(index=frame.index)
    for field in CANONICAL:
        source = mapping.get(field)
        out[field] = frame[source] if source in frame.columns else np.nan
    out["timestamp"] = pd.to_datetime(out.timestamp, errors="coerce")
    for field in ["voltage", "current", "capacity", "specific_capacity", "energy", "temperature"]:
        out[field] = pd.to_numeric(out[field], errors="coerce")
    # Preserve cycle and step identifiers, including source types and order.
    stem = re.sub(r"\.[^.]+$", "", filename)
    out["test_id"] = out.test_id.fillna(stem).astype(str)
    out["cell_id"] = out.cell_id.fillna(stem).astype(str)
    return out[CANONICAL]

def validate_frame(df: pd.DataFrame):
    issues = []
    errors = []
    if df.empty: errors.append("No data rows found")
    absent = [c for c in REQUIRED if c not in df]
    if absent: errors.append("Missing required fields: " + ", ".join(absent))
    if not any(c in df and df[c].notna().any() for c in ["capacity", "specific_capacity"]):
        errors.append("Missing required capacity data: map Capacity or Specific Capacity")
    if "timestamp" in df and df.timestamp.isna().any(): issues.append(f"{int(df.timestamp.isna().sum())} invalid or missing timestamps")
    if "timestamp" in df and df.timestamp.duplicated().any(): issues.append(f"{int(df.timestamp.duplicated().sum())} duplicate timestamps")
    for c in ["cycle", "voltage", "current", "capacity"]:
        if c in df and df[c].isna().any(): issues.append(f"{int(df[c].isna().sum())} missing/invalid {c} values")
    for c in ["energy", "temperature", "step"]:
        if c in df and df[c].isna().any(): issues.append(f"{int(df[c].isna().sum())} missing/invalid {c} values")
    if "cycle" in df:
        numeric_cycles = pd.to_numeric(df.cycle, errors="coerce")
        if (numeric_cycles.dropna() < 0).any(): errors.append("Negative cycle numbers found")
    if "voltage" in df and ((df.voltage < 0) | (df.voltage > 6)).any(): issues.append("Voltage outside expected 0–6 V range")
    if "temperature" in df and ((df.temperature < -40) | (df.temperature > 100)).any(): issues.append("Suspicious temperature outside −40–100 °C")
    if "cycle" in df and not df.cycle.dropna().empty:
        numeric = pd.to_numeric(df.cycle.dropna(), errors="coerce")
        # Gap checks only make sense for integer cycle numbers. Arbitrary
        # string identifiers are valid and must not be treated as counters.
        if len(numeric) == df.cycle.notna().sum() and np.all(np.isfinite(numeric)) and np.all(numeric % 1 == 0):
            observed = set(numeric.astype(int)); expected = set(range(min(observed), max(observed)+1))
            gaps = expected - observed
            if gaps: issues.append(f"Missing cycle numbers: {', '.join(map(str, sorted(gaps)[:10]))}")
    if "timestamp" in df and df.timestamp.notna().sum() > 1 and not df.timestamp.dropna().is_monotonic_increasing: issues.append("Timestamps are not in ascending order")
    status = "ERROR" if errors else ("WARNING" if issues else "PASS")
    return {"status": status, "errors": errors, "warnings": issues, "rows": len(df)}

def generate_demo(cell_id="CELL-A001", cycles=100, capacity_ah=5.0, fade=0.00042, seed=4):
    rng = np.random.default_rng(seed)
    rows=[]; timestamp=pd.Timestamp("2025-01-01")
    for cycle in range(1, cycles+1):
        cap=capacity_ah*(1-fade*(cycle-1))
        # Charge and discharge each have a modest number of smooth engineering samples.
        for step, direction in [(1,1),(2,-1)]:
            fractions=np.linspace(0,1,24)
            for f in fractions:
                timestamp += pd.Timedelta(seconds=150 + int(rng.integers(0,20)))
                if direction > 0:
                    voltage=3.0+1.2*f+0.12*np.tanh((f-.88)*12)
                    current=1.0
                else:
                    voltage=4.2-1.15*f-0.16*np.tanh((f-.8)*10)
                    current=-1.0
                temp=25+5*f+0.2*np.sin(cycle/8)+rng.normal(0,.12)
                rows.append((timestamp, f"TEST-{cell_id}", cell_id, None, cycle, step, None, voltage+rng.normal(0,.004), current, cap*f, np.nan, cap*f*3.65, temp))
    return pd.DataFrame(rows,columns=CANONICAL)

def demo_files():
    specs=[("CELL-A001",5.0,.00042,4),("CELL-B001",4.9,.00063,8),("CELL-C001",5.1,.00029,12)]
    result=[]
    for cell,cap,fade,seed in specs:
        df=generate_demo(cell,100,cap,fade,seed)
        # Ship demo data in a cycler-like alias format to exercise auto mapping.
        result.append((f"{cell.lower()}.xlsx",pd.DataFrame({"Time":df.timestamp,"Test ID":df.test_id,"Cell ID":df.cell_id,"Cycle Number":df.cycle,"Step":df.step,"Voltage(V)":df.voltage,"Current(A)":df.current,"Capacity(Ah)":df.capacity,"Energy(Wh)":df.energy,"Temp(C)":df.temperature})))
    return result

def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    records=[]
    for (test,cell), group in df.groupby(["test_id","cell_id"],dropna=False):
        g=group.sort_values("timestamp")
        cyc=g.groupby("cycle",dropna=True,sort=False).capacity.max().dropna()
        first=float(cyc.iloc[0]) if len(cyc) else np.nan
        latest=float(cyc.iloc[-1]) if len(cyc) else np.nan
        retention=latest/first*100 if first and np.isfinite(first) else np.nan
        # Coulombic efficiency is available only when charge/discharge capacity endpoints are separable by step.
        charge=g[g.current>0].groupby("cycle").capacity.max()
        discharge=g[g.current<0].groupby("cycle").capacity.max()
        common=charge.index.intersection(discharge.index)
        ce=(discharge.loc[common]/charge.loc[common].replace(0,np.nan)).mean()*100 if len(common) else np.nan
        records.append({"test_id":test,"cell_id":cell,"cycles":int(g.cycle.nunique()),"data_points":len(g),"average_voltage":g.voltage.mean(),"max_voltage":g.voltage.max(),"min_voltage":g.voltage.min(),"average_current":g.current.mean(),"max_current":g.current.abs().max(),"max_temperature":g.temperature.max(),"average_temperature":g.temperature.mean(),"initial_capacity_ah":first,"latest_capacity_ah":latest,"capacity_retention_pct":retention,"capacity_fade_pct":100-retention if pd.notna(retention) else np.nan,"coulombic_efficiency_pct":ce})
    return pd.DataFrame(records)

def energy_from_power(df):
    g=df.sort_values("timestamp").copy()
    if g.timestamp.isna().any() or g.timestamp.nunique()<2: return np.nan
    seconds=(g.timestamp.astype("int64")/1e9).to_numpy()
    return float(np.trapezoid((g.voltage*g.current).to_numpy(),seconds)/3600)


def normalize_step_type(value):
    """Normalize common cycler step labels without inventing missing modes."""
    if pd.isna(value) or not str(value).strip():
        return "Unknown"
    label = re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower()).strip()
    words = set(label.split())
    if "rest" in words or "idle" in words:
        return "Rest"
    direction = "Discharge" if "discharge" in words else ("Charge" if "charge" in words else None)
    if direction:
        if "cccv" in words or {"cc", "cv"}.issubset(words):
            return f"CCCV {direction}"
        if "cc" in words or "constant" in words:
            return f"CC {direction}"
        return direction
    return " ".join(word.upper() if word in {"cc", "cv", "cccv"} else word.capitalize() for word in label.split())


def with_step_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows with normalized step types and IDs for contiguous step runs."""
    out = df.copy().reset_index(drop=True)
    if "step_type" not in out:
        out["step_type"] = np.nan
    explicit = out.step_type.notna() & out.step_type.astype(str).str.strip().ne("")
    out["step_type"] = out.step_type.map(normalize_step_type)
    if "current" in out:
        current = pd.to_numeric(out.current, errors="coerce")
        inferred = pd.Series("Unknown", index=out.index, dtype=object)
        inferred.loc[current > 0] = "Charge"
        inferred.loc[current < 0] = "Discharge"
        inferred.loc[current == 0] = "Rest"
        out.loc[~explicit, "step_type"] = inferred.loc[~explicit]
    keys = [c for c in ["test_id", "cell_id", "module", "cycle", "step", "step_type"] if c in out]
    if not keys:
        out["step_block"] = np.arange(len(out))
        return out
    values = []
    for row in out[keys].itertuples(index=False, name=None):
        values.append(tuple("<missing>" if pd.isna(value) else value for value in row))
    starts = [True] + [values[i] != values[i - 1] for i in range(1, len(values))] if values else []
    out["step_block"] = np.cumsum(starts, dtype=int) - 1
    return out


def available_step_types(df: pd.DataFrame):
    if df.empty:
        return []
    return list(pd.unique(with_step_blocks(df).step_type.dropna()))


def prepare_voltage_capacity_data(df: pd.DataFrame, cycles=None, step_types=None, capacity_column="specific_capacity"):
    """Filter valid rows for a step-bounded voltage-versus-capacity chart."""
    if capacity_column not in {"specific_capacity", "capacity"} or capacity_column not in df:
        raise ValueError(f"Capacity field '{capacity_column}' is not available")
    if "cycle" not in df or ("step" not in df and "step_type" not in df):
        return df.iloc[0:0].copy(), len(df)
    out = with_step_blocks(df)
    if "step" not in out or not out.step.notna().any():
        out["step"] = out.step_type
    out["voltage"] = pd.to_numeric(out.get("voltage"), errors="coerce")
    out[capacity_column] = pd.to_numeric(out[capacity_column], errors="coerce")
    valid = out.cycle.notna() & out.step.notna() & out.voltage.notna() & out[capacity_column].notna()
    valid &= np.isfinite(out.voltage) & np.isfinite(out[capacity_column])
    skipped = int((~valid).sum())
    out = out.loc[valid].copy()
    if cycles is not None:
        out = out[out.cycle.isin(cycles)]
    if step_types is not None:
        out = out[out.step_type.isin(step_types)]
    return out, skipped


def capacity_retention_by_cycle(df: pd.DataFrame, reference_cycle, capacity_column="capacity"):
    """Calculate per-cycle max-capacity retention from an actual reference ID."""
    if capacity_column not in df:
        raise ValueError(f"Capacity field '{capacity_column}' is not available")
    if "cycle" not in df:
        return pd.DataFrame(columns=["cycle", "capacity", "retention_pct"]), len(df)
    work = df.copy()
    work[capacity_column] = pd.to_numeric(work[capacity_column], errors="coerce")
    valid = work.cycle.notna() & work[capacity_column].notna() & np.isfinite(work[capacity_column])
    skipped = int((~valid).sum())
    work = work.loc[valid]
    grouped = work.groupby("cycle", sort=False, dropna=True)[capacity_column].max()
    cycles = grouped.index.tolist()
    if reference_cycle not in grouped.index:
        return pd.DataFrame(columns=["cycle", "capacity", "retention_pct"]), skipped
    start = cycles.index(reference_cycle)
    grouped = grouped.iloc[start:]
    reference_capacity = float(grouped.iloc[0])
    result = pd.DataFrame({"cycle": grouped.index, "capacity": grouped.to_numpy()})
    result["retention_pct"] = result.capacity / reference_capacity * 100 if reference_capacity > 0 else np.nan
    return result, skipped
