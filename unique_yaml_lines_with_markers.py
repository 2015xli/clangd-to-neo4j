#!/usr/bin/env python3
import sys

def extract_unique_markers(input_file, marker):
    unique_lines = set()
    with open(input_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith(marker):
                unique_lines.add(line)
    return unique_lines

def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <input_file>")
        sys.exit(1)

    input_file = sys.argv[1]
    # marker can be any leading string like "--- !" or "  - Kind:           "
    marker = sys.argv[2] if len(sys.argv) > 2 else "  - Kind:           "
    unique_lines = extract_unique_markers(input_file, marker)

    print(f"Distinct lines starting with {marker}:")
    for line in sorted(unique_lines):
        print(line)

if __name__ == "__main__":
    main()

