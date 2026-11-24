# CSI4900 R2 -> Qt-neutral diagnostics UDP contract (independent implementation)

This is an **offline/synthetic transport adapter**, NOT an actual Xavier Qt widget or QNX live data source. Implemented in docs/Step16_Qt_Neutral_UDP_Bridge.py, with 12 contract tests and preexisting 25 metric/export tests.

## Inputs

Step10_Export_Qt_Diagnostics.py creates validated diagnostics.jsonl from the R2 analyzer and (optionally) the R1 analyzer. This Step16 bridge accepts ONLY schema csi4900.diagnostics.v1, explicit run IDs and provenance, known source/kind records, and one consistent session. It does NOT parse arbitrary serial bytes and cannot create RELEASE/COMPLETE/ISR events absent in the source stream.

## Datagram contract (v1 proposal, fully implementable by QJsonDocument)

- Each datagram is one self-contained UTF-8 compact JSON object, encoded with sorted keys for deterministic offline output.
- Schema: csi4900.udp.diagnostics.v1
- Fields: schema, sequence (zero-based), count (total datagrams), run_id, provenance (synthetic/captured/replayed), source (r1/r2), kind, data (unchanged Step10 diagnostics), diagnostics_sha256 (SHA-256 of input diagnostics.jsonl).
- No binary key material, source credentials or raw /dev/shmem contents.
- Maximum JSON datagram size 1,200 bytes, avoiding IPv4 Ethernet fragmentation with standard MTU; records above this size must be rejected rather than fragmented silently.
- Sequence and count must be validated by receiving Qt code; UDP is not reliable or ordered. Missing/reordered packets should trigger a DATA_QUALITY_GAP display, not an invented session record.
- The receiver should use QJsonDocument::fromJson(), check schema and run_id, inspect provenance to distinguish synthetic vs captured, and validate monotonically increasing sequence values. diagnostics_sha256 identifies the file input, NOT transport authentication or cryptographic integrity of the UDP channel.
- Network emissions are disabled by default; file mode emits a JSONL trace of datagrams. UDP mode targets only 127.0.0.1 by default, other IP addresses require an explicit --allow-nonloopback flag. Do not use this proposal for unauthenticated Internet streaming.

## Example usage (owner's Windows checkout)

First generate valid Step10 diagnostics.jsonl with the existing R2 analyzer and exporter using synthetic fixtures. Then:

    py -3.13 -B docs/Step16_Qt_Neutral_UDP_Bridge.py --input build/sample/diagnostics.jsonl --output-mode file --output build/sample/qt_udp_packets.jsonl

Qt UDP loopback demonstration (the receiving application must already listen at 127.0.0.1:49000):

    py -3.13 -B docs/Step16_Qt_Neutral_UDP_Bridge.py --input build/sample/diagnostics.jsonl --output-mode udp --host 127.0.0.1 --port 49000

Regression tests (no physical hardware):

    py -3.13 -m unittest tests.test_metrics_v2 tests.test_qt_export_v2 tests.test_timer_reference_v2 tests.test_r1_r2_consistency tests.test_qt_udp_bridge_v1 -v

## Integration boundary requiring Xavier
1. Xavier must provide his Qt receiver/timeline source, current UDP format and port. Only then can the actual receiver be connected to this verified envelope.
2. Agree whether live events stream individually or as diagnostic windows; this adapter currently transports *computed diagnostic outputs*, not v1 raw UART events.
3. Agree a versioned live protocol and complete RELEASE/COMPLETE/ISR/overflow/clock-epoch firmware semantics before computing full R2 measurements from live STM32 data.
4. Live QNX->Windows and actual Qt display, packet-loss behavior, and C0-C3 study remain NOT TESTED.

This independent bridge is deliberately decoupled from the collector fix PR #2 and historical STM32 Core recovery PR #3.
