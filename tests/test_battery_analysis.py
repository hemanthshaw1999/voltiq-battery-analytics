import unittest

import pandas as pd

from src.battery import (
    apply_step_type_mapping,
    available_step_types,
    capacity_retention_by_cycle,
    detect_mapping,
    demo_files,
    generate_demo,
    normalize_frame,
    normalize_step_type,
    prepare_voltage_capacity_data,
    validate_frame,
)


def sample_frame():
    return pd.DataFrame(
        {
            "test_id": ["test"] * 8,
            "cell_id": ["cell"] * 8,
            "module": [None] * 8,
            "cycle": ["111"] * 8,
            "step": [1, 10, 10, 20, 20, 30, 30, 40],
            "step_type": ["Rest", "CC-CV Discharge", "CCCV Discharge", "Rest", "Rest", "CC Charge", "CC Charge", "Rest"],
            "voltage": [3.0, 4.0, 3.9, 3.8, 3.7, 3.2, 3.4, 3.6],
            "current": [0, -1, -1, 0, 0, 1, 1, 0],
            "capacity": [0.0, 0.1, 0.2, 0.0, 0.0, 0.1, 0.2, 0.0],
            "specific_capacity": [0.0, 10.0, 20.0, 0.0, 0.0, 10.0, 20.0, 0.0],
        }
    )


class BatteryAnalysisTests(unittest.TestCase):
    def test_demo_data_still_matches_canonical_schema(self):
        demo = generate_demo(cycles=2)
        self.assertEqual(list(demo.columns), [
            "timestamp", "test_id", "cell_id", "module", "cycle", "step", "step_type",
            "voltage", "current", "capacity", "specific_capacity", "energy", "temperature",
        ])
        raw_name, raw = demo_files()[0]
        normalized = normalize_frame(raw, detect_mapping(raw.columns, raw), raw_name)
        self.assertEqual(len(normalized), 4800)

    def test_step_type_normalization_handles_common_labels(self):
        self.assertEqual(normalize_step_type("CCCV DISCHARGE"), "CCCV Discharge")
        self.assertEqual(normalize_step_type("CC-CV Discharge"), "CCCV Discharge")
        self.assertEqual(normalize_step_type("CC charge"), "CC Charge")
        self.assertEqual(normalize_step_type("Rest"), "Rest")

    def test_voltage_curve_keeps_step_boundaries_and_excludes_rest(self):
        frame = sample_frame()
        plot, skipped = prepare_voltage_capacity_data(
            frame,
            cycles=["111"],
            step_types=["CCCV Discharge", "CC Charge"],
            capacity_column="specific_capacity",
        )
        self.assertEqual(skipped, 0)
        self.assertEqual(len(plot), 4)
        self.assertEqual(set(plot.step_type), {"CCCV Discharge", "CC Charge"})
        self.assertEqual(plot.step_block.nunique(), 2)

    def test_numeric_step_ids_can_be_mapped_to_cc_and_cccv_types(self):
        frame = sample_frame().drop(columns="step_type")
        mapped = apply_step_type_mapping(
            frame,
            {10: "CCCV Discharge", 30: "CC Charge"},
        )
        plot, skipped = prepare_voltage_capacity_data(
            mapped,
            cycles=["111"],
            step_types=["CCCV Discharge", "CC Charge"],
            capacity_column="specific_capacity",
        )
        self.assertEqual(skipped, 0)
        self.assertEqual(len(plot), 4)
        self.assertEqual(set(plot.step_type), {"CCCV Discharge", "CC Charge"})
        self.assertEqual(plot.step_block.nunique(), 2)
        self.assertNotIn("step_type", frame)

    def test_step_types_are_inferred_from_current_when_labels_are_absent(self):
        frame = sample_frame().drop(columns="step_type")
        self.assertEqual(set(available_step_types(frame)), {"Rest", "Charge", "Discharge"})

    def test_invalid_measurements_are_counted_and_skipped(self):
        frame = sample_frame()
        frame.loc[1, "voltage"] = None
        frame.loc[2, "specific_capacity"] = None
        frame.loc[3, "cycle"] = None
        plot, skipped = prepare_voltage_capacity_data(
            frame, cycles=["111"], step_types=["CCCV Discharge", "CC Charge"], capacity_column="specific_capacity"
        )
        self.assertEqual(skipped, 3)
        self.assertEqual(len(plot), 2)

    def test_retention_uses_selected_nonconsecutive_string_cycle_as_reference(self):
        frame = pd.DataFrame(
            {"cycle": ["111", "222", "333"], "capacity": [5.0, 4.8, 4.5]}
        )
        result, skipped = capacity_retention_by_cycle(frame, "222")
        self.assertEqual(skipped, 0)
        self.assertEqual(result.cycle.tolist(), ["222", "333"])
        self.assertAlmostEqual(result.retention_pct.iloc[0], 100.0)
        self.assertAlmostEqual(result.retention_pct.iloc[1], 93.75)

    def test_missing_reference_capacity_returns_no_curve(self):
        frame = pd.DataFrame({"cycle": ["A", "B"], "capacity": [1.0, None]})
        result, skipped = capacity_retention_by_cycle(frame, "B")
        self.assertEqual(skipped, 1)
        self.assertTrue(result.empty)

    def test_alias_mapping_preserves_actual_cycle_and_step_identifiers(self):
        raw = pd.DataFrame(
            {
                "Time": ["2025-01-01"],
                "Cycle Number": ["cycle-Z"],
                "Step": ["CCCV Discharge"],
                "Voltage(V)": [3.7],
                "Current(A)": [-1.0],
                "Capacity(Ah)": [0.4],
            }
        )
        mapping = detect_mapping(raw.columns, raw)
        normalized = normalize_frame(raw, mapping, "cell.xlsx")
        self.assertEqual(normalized.cycle.iloc[0], "cycle-Z")
        self.assertTrue(pd.isna(normalized.step.iloc[0]))
        self.assertEqual(normalized.step_type.iloc[0], "CCCV Discharge")
        self.assertEqual(validate_frame(normalized)["status"], "WARNING")

    def test_specific_capacity_is_sufficient_when_absolute_capacity_is_absent(self):
        raw = pd.DataFrame({"Cycle Index": ["45"], "Step Index": ["7"], "Voltage": [3.8], "Specific Capacity (mAh/g)": [125.0]})
        normalized = normalize_frame(raw, detect_mapping(raw.columns, raw), "cell.xlsx")
        self.assertEqual(normalized.specific_capacity.iloc[0], 125.0)
        self.assertTrue(pd.isna(normalized.capacity.iloc[0]))


if __name__ == "__main__":
    unittest.main()
