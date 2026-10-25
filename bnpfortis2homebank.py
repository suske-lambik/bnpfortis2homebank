#!/usr/bin/env python3
"""
bnpfortis2homebank - convert a BNP Paribas Fortis CSV export to HomeBank CSV format
"""
import argparse
import csv
import os
import sys
import xml.etree.ElementTree as ET

PROG = os.path.basename(sys.argv[0])
VERSION = "1.1.1"

# HomeBank payment types, as used in the 'payment' column of its CSV import.
PAY_NONE = 0                    # none
PAY_CREDIT_CARD = 1             # credit card
PAY_CHECK = 2                   # check
PAY_CASH = 3                    # cash
PAY_BANK_TRANSFER = 4           # bank transfer
PAY_INTERNAL_TRANSFER = 5       # internal transfer
PAY_DEBIT_CARD = 6              # debit card
PAY_STANDING_ORDER = 7          # standing order
PAY_ELECTRONIC_PAYMENT = 8      # electronic payment
PAY_DEPOSIT = 9                 # deposit
PAY_FI_FEE = 10                 # financial institution fee
PAY_DIRECT_DEBIT = 11           # direct debit

# Bank transaction type ('Type verrichting') -> HomeBank payment type.
# Types not listed here get PAY_NONE and are reported as a warning.
PAYMENT_MAP = {
    "Kredietkaartbetaling": PAY_CREDIT_CARD,
    "Overschrijving in euro": PAY_BANK_TRANSFER,
    "Instantoverschrijving in euro": PAY_BANK_TRANSFER,
    "Kaartbetaling": PAY_DEBIT_CARD,
    "Doorlopende betalingsopdracht": PAY_STANDING_ORDER,
    "Kosten in verband met de rekening": PAY_FI_FEE,
    "Domiciliëring": PAY_DIRECT_DEBIT,
    "Hypotheekleningen Terugbetalingen": PAY_DIRECT_DEBIT,
    "Diverse Debetverrichtingen": PAY_DEBIT_CARD,
    "Geldopname met kaart": PAY_CASH,
    "Geldopname in buitenland": PAY_CASH,
}

OUT_HEADER = ["date", "payment", "number", "payee", "memo", "amount", "category", "tags"]

DESCRIPTION = """\
Convert a BNP Paribas Fortis CSV export (';'-separated, BOM and spaces in
header names are handled) into HomeBank's CSV import format:
  date;payment;number;payee;memo;amount;category;tags

With --xhb, transactions whose sequence number (Volgnummer) is already present
in the given HomeBank file are skipped, so overlapping exports can be
converted safely. The HomeBank file is only read, never modified."""

EPILOG = f"""\
Dates are written as yyyy-mm-dd: choose "y-m-d" in HomeBank's import dialog.
Transactions with an unknown 'Type_verrichting' get payment 0 and are
reported on standard error.

Examples:
  {PROG} CSV_2026-10-18-07.52.csv > import.csv
  {PROG} -o import.csv CSV_2026-10-18-07.52.csv
  {PROG} -x finances.xhb -a "Zichtrekening" -o import.csv CSV_2026-10-18-07.52.csv"""


def die(msg, code=1):
    print(f"{PROG}: {msg}", file=sys.stderr)
    sys.exit(code)


def warn(msg):
    print(f"{PROG}: {msg}", file=sys.stderr)


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
    p.add_argument("-x", "--xhb", metavar="FILE.xhb",
                   help="skip transactions whose Volgnummer already exists "
                        "in this HomeBank file")
    p.add_argument("-a", "--account", metavar="NAME",
                   help="with --xhb: only compare against transactions of "
                        "the HomeBank account named NAME")
    p.add_argument("-q", "--quiet", action="store_true",
                   help="with --xhb: do not list each skipped duplicate")
    p.add_argument("-V", "--version", action="version",
                   version=f"{PROG} {VERSION}")
    args = p.parse_args()
    if args.account and not args.xhb:
        p.error("--account requires --xhb")
    return args


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


def read_xhb_numbers(path, account_name=None):
    """Return the set of 'info' values (HomeBank's number field) of the
    transactions in a HomeBank .xhb file, optionally limited to one account."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as e:
        die(f"cannot parse HomeBank file {path}: {e}")
    except OSError as e:
        die(f"cannot read HomeBank file {path}: {e.strerror}")

    if root.tag != "homebank":
        die(f"not a HomeBank file: {path}")

    account_key = None
    if account_name is not None:
        accounts = {a.get("name"): a.get("key") for a in root.iter("account")}
        if account_name not in accounts:
            names = ", ".join(sorted(n for n in accounts if n)) or "(none)"
            die(f"account not found in {path}: {account_name}\n"
                f"  available accounts: {names}")
        account_key = accounts[account_name]

    numbers = set()
    for ope in root.iter("ope"):
        if account_key is not None and ope.get("account") != account_key:
            continue
        info = (ope.get("info") or "").strip()
        if info:
            numbers.add(info)
    return numbers


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
    if args.xhb and not os.path.isfile(args.xhb):
        die(f"file not found: {args.xhb}")
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

    existing = read_xhb_numbers(args.xhb, args.account) if args.xhb else None

    # Warn about transaction types not covered by the mapping
    unknown = []
    for r in rows:
        t = r["Type_verrichting"]
        if t not in PAYMENT_MAP and t not in unknown:
            unknown.append(t)
    if unknown:
        warn("warning: unmapped transaction types (payment set to 0):")
        for t in unknown:
            print(f"  {t}", file=sys.stderr)

    lines = []
    if not args.no_header:
        lines.append(";".join(OUT_HEADER))
    count = 0
    duplicates = []      # (row, reason)
    no_number = 0
    seen_in_input = set()

    for r in rows:
        if not args.include_refused and r["Reden_van_weigering"].strip():
            continue

        number = r["Volgnummer"].strip()
        if existing is not None:
            if not number:
                no_number += 1
            elif number in existing:
                duplicates.append((r, "already in HomeBank"))
                continue
            elif number in seen_in_input:
                duplicates.append((r, "repeated in input"))
                continue
            seen_in_input.add(number)

        memo = r["Mededeling"] or r["Details"]
        lines.append(";".join([
            to_iso_date(r[date_col]),
            str(PAYMENT_MAP.get(r["Type_verrichting"], PAY_NONE)),
            number,
            clean(r["Naam_van_de_tegenpartij"]),
            clean(memo),
            to_amount(r["Bedrag"]),
            "",
            "",
        ]))
        count += 1

    if existing is not None:
        if duplicates:
            warn(f"skipped {len(duplicates)} duplicate transaction(s)")
            if not args.quiet:
                for r, reason in duplicates:
                    print(f"  {r['Volgnummer']}  {to_iso_date(r[date_col])}  "
                          f"{to_amount(r['Bedrag']):>10}  "
                          f"{r['Naam_van_de_tegenpartij']}  ({reason})",
                          file=sys.stderr)
        if no_number:
            warn(f"warning: {no_number} transaction(s) without Volgnummer "
                 "could not be checked for duplicates and were included")

    text = "\n".join(lines) + ("\n" if lines else "")
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        warn(f"wrote {count} transactions to {args.output}")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.write(text)
        if existing is not None:
            warn(f"wrote {count} transactions")


if __name__ == "__main__":
    main()