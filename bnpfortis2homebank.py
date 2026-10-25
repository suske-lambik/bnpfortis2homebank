#!/usr/bin/env python3
"""
bnpfortis2homebank - convert a BNP Paribas Fortis CSV export to HomeBank CSV format
"""
import argparse
import csv
import os
import sys

PROG = os.path.basename(sys.argv[0])
VERSION = "1.0.0"

PAYMENT_MAP = {
    "Kredietkaartbetaling": 1,
    "Overschrijving in euro": 4,
    "Instantoverschrijving in euro": 4,
    "Kaartbetaling": 6,
    "Doorlopende betalingsopdracht": 7,
    "Kosten in verband met de rekening": 10,
    "Domiciliëring": 11,
    "Hypotheekleningen Terugbetalingen": 11,
}

OUT_HEADER = ["date", "payment", "number", "payee", "memo", "amount", "category", "tags"]

DESCRIPTION = """\
Convert a BNP Paribas Fortis CSV export (';'-separated, BOM and spaces in
header names are handled) into HomeBank's CSV import format:
  date;payment;number;payee;memo;amount;category;tags"""

EPILOG = f"""\
Dates are written as yyyy-mm-dd: choose "y-m-d" in HomeBank's import dialog.
Transactions with an unknown 'Type_verrichting' get payment 0 and are
reported on standard error.

Examples:
  {PROG} CSV_2026-10-18-07.52.csv > import.csv
  {PROG} -o import.csv CSV_2026-10-18-07.52.csv"""


def die(msg, code=1):
    print(f"{PROG}: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_args():
    p = argparse.ArgumentParser(
        prog=PROG,
        description=DESCRIPTION,
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("input", metavar="INPUT.csv")
    p.add_argument("-o", "--output", metavar="FILE",
                   help="write to FILE instead of standard output")
    p.add_argument("-f", "--force", action="store_true",
                   help="overwrite FILE if it already exists")
    p.add_argument("-v", "--value-date", action="store_true",
                   help="use Valutadatum instead of Uitvoeringsdatum as date")
    p.add_argument("-r", "--include-refused", action="store_true",
                   help="also include refused transactions")
    p.add_argument("-n", "--no-header", action="store_true",
                   help="do not write the header line")
    p.add_argument("-V", "--version", action="version",
                   version=f"{PROG} {VERSION}")
    return p.parse_args()


def read_rows(path):
    """Read the export, stripping the BOM and turning spaces in header names
    into underscores, so both the raw bank export and an edited copy work."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f, delimiter=";")
        try:
            header = next(reader)
        except StopIteration:
            die(f"input file is empty: {path}")
        keys = [h.strip().replace(" ", "_") for h in header]
        rows = []
        for fields in reader:
            if not any(fld.strip() for fld in fields):
                continue  # skip blank lines
            fields += [""] * (len(keys) - len(fields))
            rows.append(dict(zip(keys, fields)))
    return keys, rows


def to_iso_date(d):
    """dd/mm/yyyy -> yyyy-mm-dd"""
    return f"{d[6:10]}-{d[3:5]}-{d[0:2]}"


def to_amount(s):
    """Format the amount with two decimals; accepts '1234.5' and '1.234,50'."""
    s = (s or "").strip().replace(" ", "")
    if not s:
        return "0.00"
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return f"{float(s):.2f}"
    except ValueError:
        return "0.00"


def clean(s):
    return (s or "").replace(";", ",")


def main():
    args = parse_args()

    if not os.path.isfile(args.input):
        die(f"file not found: {args.input}")
    if not os.access(args.input, os.R_OK):
        die(f"file not readable: {args.input}")
    if args.output and os.path.exists(args.output) and not args.force:
        die(f"output file exists: {args.output} (use --force to overwrite)")

    date_col = "Valutadatum" if args.value_date else "Uitvoeringsdatum"

    try:
        keys, rows = read_rows(args.input)
    except UnicodeDecodeError:
        die(f"input is not valid UTF-8: {args.input}")

    required = {date_col, "Type_verrichting", "Volgnummer", "Bedrag",
                "Naam_van_de_tegenpartij", "Mededeling", "Details"}
    if not args.include_refused:
        required.add("Reden_van_weigering")
    missing = sorted(required - set(keys))
    if missing:
        die("missing column(s) in input: " + ", ".join(missing))

    # Warn about transaction types not covered by the mapping
    unknown = []
    for r in rows:
        t = r["Type_verrichting"]
        if t not in PAYMENT_MAP and t not in unknown:
            unknown.append(t)
    if unknown:
        print(f"{PROG}: warning: unmapped transaction types (payment set to 0):",
              file=sys.stderr)
        for t in unknown:
            print(f"  {t}", file=sys.stderr)

    lines = []
    if not args.no_header:
        lines.append(";".join(OUT_HEADER))
    count = 0
    for r in rows:
        if not args.include_refused and r["Reden_van_weigering"].strip():
            continue
        memo = r["Mededeling"] or r["Details"]
        lines.append(";".join([
            to_iso_date(r[date_col]),
            str(PAYMENT_MAP.get(r["Type_verrichting"], 0)),
            r["Volgnummer"],
            clean(r["Naam_van_de_tegenpartij"]),
            clean(memo),
            to_amount(r["Bedrag"]),
            "",
            "",
        ]))
        count += 1

    text = "\n".join(lines) + ("\n" if lines else "")
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        print(f"{PROG}: wrote {count} transactions to {args.output}", file=sys.stderr)
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)


if __name__ == "__main__":
    main()