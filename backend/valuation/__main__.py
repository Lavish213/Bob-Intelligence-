import argparse
import json
from pathlib import Path
import sys

from backend.valuation.engine import compare_sales


def main():
    parser = argparse.ArgumentParser(description='Calculate an advisory valuation from reviewed comparable-sale evidence.')
    parser.add_argument('input_json', type=Path)
    args = parser.parse_args()
    try:
        if args.input_json.stat().st_size > 2000000:
            raise ValueError('Input budget exceeded')
        result = compare_sales(json.loads(args.input_json.read_text()))
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        json.dump({'status': 'invalid_input', 'quote_authorized': False, 'offer_authorized': False}, sys.stdout)
        sys.stdout.write('\n')
        return 2
    json.dump(result, sys.stdout, indent=2, allow_nan=False)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
