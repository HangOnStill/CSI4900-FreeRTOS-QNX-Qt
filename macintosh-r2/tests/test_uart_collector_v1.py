"""CSI4900 v1 collector host-fixture contract tests.
Frames mirror Xavier's trace_transport.c: sync A5 5A, version 1,
length = 10 + 13*n, sequence LE32, count, 13-byte events, CCITT-FALSE CRC.
Synthetic evidence only. Nothing here tests the physical UART or QNX driver.
"""
import binascii
import subprocess
import struct
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/"build"/"uart_collector_v1_host.exe"

def task_hash(name):
    out=2166136261
    for byte in name.encode("ascii"):
        out=((out ^ byte)*16777619) & 0xffffffff
    return out

SENSOR=task_hash("SensorTask")
CONTROL=task_hash("ControlTask")
OTHER=task_hash("UnknownThread")

def event(kind,task,cycles,parameter=0):
    return struct.pack("<BIII",kind,task,cycles,parameter)

def frame(seq,*events):
    assert 1<=len(events)<=8
    n=len(events)
    payload=(b"\xa5\x5a"+bytes([1])+struct.pack("<H",10+13*n)
         +struct.pack("<I",seq)+bytes([n])+b"".join(events))
    crc=binascii.crc_hqx(payload[2:],0xffff)
    return payload+struct.pack("<H",crc)

def invoke(blob,cycles=16):
    with tempfile.TemporaryDirectory() as work:
        path=Path(work)/"trace.bin"
        path.write_bytes(blob)
        return subprocess.run([str(EXE),"--fixture",str(path),"--cycles-per-us",str(cycles)],
                              capture_output=True,text=True,timeout=8)

class CollectorV1(unittest.TestCase):
    def test_00_binary_exists(self):
        self.assertTrue(EXE.is_file())

    def test_01_valid_two_frames_and_ids(self):
        wire=(frame(0,event(1,SENSOR,160),event(2,SENSOR,320))
             +frame(1,event(1,CONTROL,480),event(2,CONTROL,640)))
        p=invoke(wire)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(p.stdout.splitlines(),
            ["0,SWITCH_IN,1","10,SWITCH_OUT,1",
             "20,SWITCH_IN,2","30,SWITCH_OUT,2"])
        self.assertIn("frames=2 crc_errors=0 frame_gaps=0 invalid_frames=0",p.stderr)

    def test_02_max_eight_events_frame(self):
        wire=frame(0,*[event(1 if i%2==0 else 2,SENSOR,160*i)
                       for i in range(8)])
        p=invoke(wire)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual(len(p.stdout.splitlines()),8)

    def test_03_crc_corruption_is_rejected(self):
        bad=bytearray(frame(0,event(1,SENSOR,160)))
        bad[-1]^=0x33
        p=invoke(bytes(bad))
        self.assertNotEqual(p.returncode,0)
        self.assertIn("crc_errors=1",p.stderr)
        self.assertIn("GAP",p.stdout)

    def test_04_frame_sequence_gap_from_zero_detected(self):
        wire=(frame(0,event(1,SENSOR,160))
              +frame(2,event(2,SENSOR,320)))
        p=invoke(wire)
        self.assertIn("frame_gaps=1",p.stderr)
        self.assertIn("GAP",p.stdout)

    def test_05_gap_timestamp_does_not_reverse(self):
        wire=(frame(0,event(1,SENSOR,160),event(2,SENSOR,320))
              +frame(2,event(1,SENSOR,480)))
        p=invoke(wire)
        lines=p.stdout.splitlines()
        gaps=[int(line.split(",")[0]) for line in lines if ",GAP," in line]
        self.assertTrue(gaps)
        stamps=[int(line.split(",")[0]) for line in lines]
        self.assertEqual(stamps,sorted(stamps),
                         "GAP timestamps must not reverse after previous emitted events")

    def test_06_truncated_final_frame_rejected(self):
        wire=frame(0,event(1,SENSOR,160))[:-7]
        p=invoke(wire)
        self.assertNotEqual(p.returncode,0,"Truncated capture must not return success")
        self.assertIn("GAP",p.stdout)

    def test_07_unrecognized_event_does_not_pass_silently(self):
        wire=frame(0,event(19,SENSOR,160))
        p=invoke(wire)
        self.assertNotEqual(p.returncode,0,
                          "Unsupported event must not be accepted as complete data")
        self.assertIn("GAP",p.stdout)

    def test_08_crc_corruption_around_valid_frames(self):
        bad=bytearray(frame(1,event(2,SENSOR,480)));bad[-2]^=0x12
        wire=(frame(0,event(1,SENSOR,160),event(2,SENSOR,320))
              +bytes(bad)+frame(2,event(1,SENSOR,640)))
        p=invoke(wire)
        self.assertNotEqual(p.returncode,0)
        stamps=[int(line.split(",")[0]) for line in p.stdout.splitlines()]
        self.assertEqual(stamps,sorted(stamps))
        self.assertIn("crc_errors=1",p.stderr)

    def test_09_fractional_cycle_carry(self):
        wire=frame(0,*[event(1 if i%2==0 else 2,SENSOR,i)
                       for i in range(8)])
        p=invoke(wire,cycles=4)
        self.assertEqual(p.returncode,0)
        stamps=[int(line.split(",")[0]) for line in p.stdout.splitlines()]
        self.assertEqual(stamps,[0,0,0,0,1,1,1,1])

    def test_10_cycle_wrap_near_uint32(self):
        wire=frame(0,event(1,SENSOR,0xfffffff0),
                      event(2,SENSOR,0x10))
        p=invoke(wire,cycles=16)
        self.assertEqual(p.returncode,0)
        self.assertEqual(p.stdout.splitlines(),
                         ["0,SWITCH_IN,1","2,SWITCH_OUT,1"])

    def test_11_invalid_cli_frequency_fails(self):
        p=invoke(frame(0,event(1,SENSOR,160)),cycles=0)
        self.assertEqual(p.returncode,2)

if __name__=="__main__":
    unittest.main()
