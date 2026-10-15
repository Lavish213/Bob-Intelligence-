import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.valuation.local_benchmark import evaluate


def main():
    parser = argparse.ArgumentParser(description='Evaluate frozen local valuation requests against separately supplied closed-sale outcomes; never grants production authority.')
    parser.add_argument('input_json', type=Path)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--evaluated-on', required=True)
    args = parser.parse_args()
    try:
        with args.input_json.open('rb') as source:
            raw = source.read(10000001)
        if len(raw) > 10000000:
            raise ValueError('Input budget exceeded')
        if hashlib.sha256(raw).hexdigest() != args.expected_sha256:
            raise ValueError('Dataset checksum differs from frozen cohort')
        result = evaluate(json.loads(raw), args.evaluated_on)
    except (OSError, ValueError, TypeError, KeyError, RecursionError, ArithmeticError):
        json.dump({'status': 'invalid_input', 'production_ready': False, 'quote_authorized': False, 'offer_authorized': False}, sys.stdout)
        sys.stdout.write('\n')
        return 2
    json.dump(result, sys.stdout, indent=2, allow_nan=False)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
