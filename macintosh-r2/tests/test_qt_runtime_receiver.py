"""Actual QtCore JSON + QtNetwork QUdpSocket receiver integration tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

DOCS=Path(__file__).resolve().parents[1]/"docs"
sys.path.insert(0,str(DOCS))
import Step16_Qt_Neutral_UDP_Bridge as bridge
try:
    import Step20_Qt_Receiver_Reference as qt
except ModuleNotFoundError as exc:
    if exc.name != "PySide6" and not (exc.name or "").startswith("PySide6."):
        raise
    qt = None

def rec(name="session",qual="COMPLETE",unknown=0):
    return {
      "schema":"csi4900.diagnostics.v1",
      "run_id":"test_session",
      "provenance":"synthetic",
      "source":"r2",
      "kind":name,
      "data":{"quality":qual,"unknown_us":unknown,"elapsed_us":100}
    }
def packet(record,seq=0,count=1,digest="a"*64):
    return json.dumps({
        "schema":qt.WIRE_SCHEMA,
        "sequence":seq,"count":count,
        "run_id":record["run_id"],"provenance":record["provenance"],
        "source":record["source"],"kind":record["kind"],"data":record["data"],
        "diagnostics_sha256":digest,
    },sort_keys=True,separators=(",",":")).encode()

@unittest.skipUnless(qt is not None, "Install pinned PySide6-Essentials to run Qt runtime tests")
class RealQtReceiver(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"data.jsonl"
        rows=[rec("utilization_window"),rec("session")]
        self.path.write_text("".join(json.dumps(r)+"\n" for r in rows))
        self.actual_packets=bridge.prepare(self.path)

    def test_qt_doc_parses_actual_packets(self):
        data=qt.qt_file_parse(self.actual_packets)
        self.assertEqual(data["packets"],2)
        self.assertEqual(data["status"],"PASS")
        self.assertFalse(data["qt_production_application_tested"])

    def test_actual_qt_udp_receives_loopback(self):
        data=qt.qt_udp_loopback(self.actual_packets)
        self.assertEqual(data["packets"],2)
        self.assertIn("QUdpSocket",data["delivery"])

    def test_qt_preserves_partial_unknown(self):
        row=rec("utilization_window",qual="PARTIAL",unknown=42)
        raw=packet(row)
        doc=qt.qt_json_parse(raw)
        self.assertEqual(doc["data"]["unknown_us"],42)
        self.assertEqual(doc["data"]["quality"],"PARTIAL")
        session=qt.QtReferenceSession()
        session.consume(raw)
        self.assertEqual(session.summary()["quality_flags"],["PARTIAL"])

    def test_missing_packet_rejected(self):
        session=qt.QtReferenceSession()
        session.consume(self.actual_packets[0])
        with self.assertRaisesRegex(ValueError,"missing"):
            session.summary()

    def test_duplicate_packet_rejected(self):
        session=qt.QtReferenceSession()
        session.consume(self.actual_packets[0])
        with self.assertRaisesRegex(ValueError,"reordered|duplicate"):
            session.consume(self.actual_packets[0])

    def test_reordered_packet_rejected(self):
        session=qt.QtReferenceSession()
        with self.assertRaisesRegex(ValueError,"reordered"):
            session.consume(self.actual_packets[1])

    def test_qt_incompatible_schema_rejected(self):
        p=json.loads(self.actual_packets[0])
        p["schema"]="bad.wire"
        with self.assertRaisesRegex(ValueError,"incompatible"):
            qt.QtReferenceSession().consume(json.dumps(p).encode())

    def test_qt_unknown_type_rejected(self):
        p=json.loads(self.actual_packets[0])
        p["kind"]="made_up"
        with self.assertRaisesRegex(ValueError,"unknown source or event"):
            qt.QtReferenceSession().consume(json.dumps(p).encode())

    def test_qt_malformed_json_rejected(self):
        with self.assertRaisesRegex(ValueError,"Malformed"):
            qt.qt_json_parse(b"{not valid}")

    def test_oversized_packet_rejected(self):
        with self.assertRaisesRegex(ValueError,"1..1200"):
            qt.qt_json_parse(b"x"*1201)

    def test_cross_run_rejected(self):
        session=qt.QtReferenceSession()
        session.consume(self.actual_packets[0])
        second=json.loads(self.actual_packets[1])
        second["run_id"]="different"
        with self.assertRaisesRegex(ValueError,"inconsistent"):
            session.consume(json.dumps(second).encode())

    def test_mixed_source_hash_rejected(self):
        session=qt.QtReferenceSession()
        session.consume(self.actual_packets[0])
        second=json.loads(self.actual_packets[1])
        second["diagnostics_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"inconsistent"):
            session.consume(json.dumps(second).encode())

    def test_file_reader_rejects_empty(self):
        self.path.write_bytes(b"")
        with self.assertRaisesRegex(ValueError,"Missing"):
            qt.read_packets(self.path)

    def test_qt_session_parses_multiple_calls(self):
        first=qt.qt_udp_loopback(self.actual_packets)
        second=qt.qt_udp_loopback(self.actual_packets)
        self.assertEqual(first["source_sha256"],second["source_sha256"])

if __name__=="__main__":
    unittest.main()
