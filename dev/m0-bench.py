#!/usr/bin/env python3
"""Measure parse through both artifacts on disk, excluding interpreter startup."""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('tether_driver', ROOT / 'bin/driver.py')
driver = importlib.util.module_from_spec(spec)
spec.loader.exec_module(driver)
BOUND_MS = 150.0


def measure(source_root, source, work, runs=5):
    samples = []
    for index in range(runs + 1):
        code, ms = driver.emit(source_root, source, work / f'run-{index}')
        if code or ms is None or not math.isfinite(ms) or ms < 0:
            raise ValueError(f'Compile failed: exit={code}')
        if index:
            samples.append(ms)
    return samples


def report(samples):
    if len(samples) != 5 or any(not math.isfinite(n) or n < 0 for n in samples):
        raise ValueError('M0-TIME needs five finite samples')
    median = statistics.median(samples)
    print(f'BENCH m0-time median_ms={median:.3f} min_ms={min(samples):.3f} '
          f'max_ms={max(samples):.3f} runs=5', flush=True)
    passed = median < BOUND_MS
    print(f'{"PASS" if passed else "FAIL"} M0-TIME median_ms={median:.3f} bound_ms=150', flush=True)
    return passed


def tcc_ms(source, target):
    start = time.perf_counter_ns()
    subprocess.run(['tcc', '-c', '-o', str(target), str(source)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=30)
    return (time.perf_counter_ns() - start) / 1000000


def ratio(samples, source_root, source, work, started):
    data = (ROOT / 'dev/denominators.json').read_bytes()
    manifest = dict((path, digest) for digest, path in
                    (row.split() for row in (ROOT / 'dev/DENOMINATORS.sha256').read_text().splitlines()))
    expected = manifest.get('dev/denominators.json')
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError('DENOMINATORS hash mismatch')
    denominators = json.loads(data)
    empty = work / 'empty.c'
    empty.write_bytes(b'')
    # Fresh output and process for each sample, with one warm-up per source.
    raw, fixed = [], []
    for index in range(6):
        a = tcc_ms(ROOT / 'corpus/twin/spine.c', work / f'spine-{index}.o')
        b = tcc_ms(empty, work / f'empty-{index}.o')
        if index:
            raw.append(a)
            fixed.append(b)
    elapsed = time.monotonic() - started
    if elapsed >= 60:
        raise ValueError(f'RATIO-WINDOW measurement span {elapsed:.3f}s exceeds 60s')
    lines = len((source_root / source).read_text().splitlines())
    c_lines = len((ROOT / 'corpus/twin/spine.c').read_text().splitlines())
    rate = statistics.median(samples) * 1000 / lines
    values = [denominators[key]['value'] for key in
              ('tcc_raw_ms_per_kloc', 'tcc_corrected_ms_per_kloc', 'trice_end_to_end_ms_per_kloc')]
    if any(not math.isfinite(v) or v <= 0 for v in values):
        raise ValueError('DENOMINATORS must be positive finite values')
    print(f'M0-TCC-RATIO raw={rate / values[0]:.3f} corrected={rate / values[1]:.3f} '
          f'end_to_end={rate / values[2]:.3f} programs=1 source=frozen informational=1')
    raw_rate = statistics.median(raw) * 1000 / c_lines
    print(f'TCC-LIVE median_ms={statistics.median(raw):.3f} empty_ms={statistics.median(fixed):.3f} '
          f'raw_ratio={rate / raw_rate:.3f} span_s={elapsed:.3f} programs=1 runs=5')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ratio', action='store_true')
    parser.add_argument('--source-root', type=Path, default=ROOT / 'examples')
    parser.add_argument('--source', default='M0Spine.tet')
    args = parser.parse_args()
    try:
        print('LOAD ' + subprocess.check_output(['uptime'], text=True).strip(), flush=True)
        with tempfile.TemporaryDirectory(prefix='tether-bench-') as directory:
            work = Path(directory)
            started = time.monotonic()
            samples = measure(args.source_root, args.source, work)
            passed = report(samples)
            if args.ratio:
                ratio(samples, args.source_root, args.source, work, started)
            fixed_root = work / 'fixed'
            fixed_root.mkdir()
            # Both fixtures still emit a failing Client and the full reactor.
            (fixed_root / 'Fixed.tet').write_text('module Fixed\ndef main : Client Reply := fail Reply Busy\n')
            fixed = statistics.median(measure(fixed_root, 'Fixed.tet', fixed_root / 'base'))
            extra = ''.join(f'def fixed{i} : Nat := {i}\n' for i in range(100))
            (fixed_root / 'Fixed.tet').write_text('module Fixed\n' + extra +
                                                'def main : Client Reply := fail Reply Busy\n')
            expanded = statistics.median(measure(fixed_root, 'Fixed.tet', fixed_root / 'expanded'))
            print(f'FIXED-MS fixed_ms={fixed:.3f} per_def_ms={(expanded - fixed) / 100:.3f} '
                  'added_definitions=100 informational=1')
            return 0 if passed else 1
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f'FAIL M0-BENCH {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
