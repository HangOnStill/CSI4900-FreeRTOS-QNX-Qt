"""Expected v1-to-R2 incompatibility checks, not live hardware evidence."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from .test_uart_collector_v1 import frame, event, SENSOR, CONTROL, OTHER, EXE, ROOT

METRICS=ROOT/"build"/"trace_metrics_v2_host.exe"
CONFIG=ROOT/"fixtures"/"config.csv"

def collect_and_analyze(data):
    with tempfile.TemporaryDirectory() as temp:
        source=Path(temp)/"v1_capture.bin"
        decoded=Path(temp)/"events.csv"
        source.write_bytes(data)
        result=subprocess.run(
            [str(EXE),"--fixture",str(source),"--output",str(decoded)],
            capture_output=True,text=True,timeout=8)
        analyzer=subprocess.run(
            [str(METRICS),str(CONFIG),str(decoded),"100"],
            capture_output=True,text=True,timeout=8)
        return result,analyzer,decoded.read_text(encoding="utf-8")

class V1CompatibilityTests(unittest.TestCase):
    def test_switch_only_stream_fails_r2_without_release(self):
        col,ana,data=collect_and_analyze(
            frame(0,event(1,SENSOR,160),event(2,SENSOR,320)))
        self.assertEqual(col.returncode,0,col.stderr)
        self.assertIn("SWITCH_IN",data)
        self.assertEqual(ana.returncode,1)
        self.assertIn("INVALID_SWITCH_IN",ana.stdout)

    def test_unconfigured_task_id_rejected(self):
        col,ana,data=collect_and_analyze(
            frame(0,event(1,OTHER,160),event(2,OTHER,320)))
        self.assertEqual(col.returncode,0,col.stderr)
        self.assertIn(",SWITCH_IN,5",data)
        self.assertEqual(ana.returncode,1)
        self.assertIn("UNKNOWN_TASK",ana.stdout)

    def test_event_stream_requires_releases_even_with_known_ids(self):
        wire=(frame(0,event(1,SENSOR,160),event(2,SENSOR,320))+
              frame(1,event(1,CONTROL,480),event(2,CONTROL,640)))
        col,ana,data=collect_and_analyze(wire)
        self.assertEqual(col.returncode,0,col.stderr)
        self.assertEqual(len(data.splitlines()),4)
        self.assertEqual(ana.returncode,1)
        self.assertIn("INVALID_SWITCH_IN",ana.stdout)

if __name__=="__main__":
    unittest.main()
