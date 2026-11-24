"""M8 timer comparison tests: synthetic data only."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"docs"))
from Step11_Timing_Reference_Compare import compare, export
SOURCE=ROOT/"fixtures"/"r2_timer_reference_synthetic.csv"
class TimerReferenceTests(unittest.TestCase):
    def test_reference_interval_errors(self):
        rows,summary=compare(SOURCE)
        self.assertEqual(len(rows),3)
        self.assertEqual([row["signed_error_us"] for row in rows],[0,4,1])
        self.assertEqual(summary["max_absolute_error_us"],4)
        self.assertEqual(summary["paired_intervals"],3)
    def test_export_does_not_claim_hardware(self):
        with tempfile.TemporaryDirectory() as td:
            info=export(SOURCE,td,"synthetic")
            self.assertEqual(info["provenance"],"synthetic")
            self.assertTrue((Path(td)/"timer_reference_errors.csv").is_file())
    def test_reversal_fails(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"bad.csv"
            source.write_text(
                "run_id,marker,trace_us,reference_us,reference_overhead_us\n"
                "a,x,100,1000,0\n"
                "a,y,90,2000,0\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"non-monotonic"):
                compare(source)
    def test_missing_reference_data_fails(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"bad.csv";source.write_text("trace_us\n100\n",encoding="utf-8")
            with self.assertRaisesRegex(ValueError,"Missing"):
                compare(source)
if __name__=="__main__":unittest.main()
