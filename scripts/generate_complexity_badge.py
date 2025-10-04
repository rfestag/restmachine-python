#!/usr/bin/env python3
"""Generate a code complexity badge from radon output."""

import re
import subprocess
import sys
from pathlib import Path

import anybadge


def get_complexity_rating():
    """Run radon and extract the average complexity rating."""
    try:
        result = subprocess.run(
            [
                "radon",
                "cc",
                "packages/restmachine/src/restmachine",
                "packages/restmachine-aws/src/restmachine_aws",
                "--total-average",
            ],
            capture_output=True,
            text=True,
            check=True,
        )

        output = result.stdout

        # Look for "Average complexity: A (3.xx)" pattern
        match = re.search(r"Average complexity:\s+([A-F])\s+\(([0-9.]+)\)", output)

        if match:
            rating = match.group(1)
            score = float(match.group(2))
            return rating, score
        else:
            print("Could not parse radon output", file=sys.stderr)
            print(output, file=sys.stderr)
            return None, None

    except subprocess.CalledProcessError as e:
        print(f"Error running radon: {e}", file=sys.stderr)
        print(e.stdout, file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        return None, None


def generate_badge(rating, score):
    """Generate a badge SVG file."""
    # Define color thresholds based on radon ratings
    thresholds = {
        'A': {'color': '#4c1', 'label': 'excellent'},      # green
        'B': {'color': '#97CA00', 'label': 'good'},        # light green
        'C': {'color': '#dfb317', 'label': 'moderate'},    # yellow
        'D': {'color': '#fe7d37', 'label': 'complex'},     # orange
        'E': {'color': '#e05d44', 'label': 'very complex'},# red
        'F': {'color': '#e05d44', 'label': 'unmaintainable'},# red
    }

    rating_info = thresholds.get(rating, thresholds['C'])

    badge = anybadge.Badge(
        label='code quality',
        value=f'{rating} ({score:.2f})',
        default_color=rating_info['color']
    )

    output_file = Path("complexity-badge.svg")
    badge.write_badge(str(output_file), overwrite=True)
    print(f"Badge generated: {output_file}")
    print(f"Rating: {rating} ({rating_info['label']}) - Score: {score:.2f}")


def main():
    """Main entry point."""
    rating, score = get_complexity_rating()

    if rating is None or score is None:
        sys.exit(1)

    generate_badge(rating, score)


if __name__ == "__main__":
    main()
