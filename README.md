# bnpfortis2homebank

Convert a **BNP Paribas Fortis** CSV export into the CSV import format of
[HomeBank](https://www.gethomebank.org/), the free personal finance manager.

> This project is not affiliated with, endorsed by or sponsored by
> BNP Paribas Fortis or the HomeBank project. Product names are used only to
> describe the file formats this tool converts.

The bank export (Dutch-language) is converted to HomeBank's 8-column format:

```
date;payment;number;payee;memo;amount;category;tags
```

## Features

- Works directly on the file downloaded from the bank. The UTF-8 BOM, spaces
  in column names and Windows line endings are handled automatically.
- Maps the bank's transaction types to HomeBank payment types.
- Converts dates to ISO format (`yyyy-mm-dd`).
- Accepts amounts with either a `.` or a `,` decimal separator.
- Skips refused transactions by default.
- Uses the message (`Mededeling`) as memo, falling back to `Details` when empty
  (useful for card payments).
- Warns about transaction types it doesn't know yet.
- Reports missing columns by name instead of failing obscurely.

## Requirements

- Python 3.7 or later. Only the standard library is used; there is nothing
  else to install.

Runs on Linux, macOS and Windows.

## Installation

```bash
git clone https://github.com/<your-user>/bnpfortis2homebank.git
cd bnpfortis2homebank
install -m 755 bnpfortis2homebank.py ~/.local/bin/bnpfortis2homebank
```

Make sure `~/.local/bin` is in your `PATH`.

On Windows, or without installing, run it through Python:

```bash
python3 bnpfortis2homebank.py [OPTIONS] INPUT.csv
```

## Usage

```
bnpfortis2homebank [OPTIONS] INPUT.csv
```

| Option | Description |
|---|---|
| `-o`, `--output FILE` | Write to `FILE` instead of standard output |
| `-f`, `--force` | Overwrite `FILE` if it already exists |
| `-v`, `--value-date` | Use the value date (`Valutadatum`) instead of the execution date (`Uitvoeringsdatum`) |
| `-r`, `--include-refused` | Also include refused transactions |
| `-n`, `--no-header` | Do not write the header line |
| `-h`, `--help` | Show help and exit |
| `-V`, `--version` | Show version and exit |

### Examples

```bash
# Print the converted transactions
bnpfortis2homebank CSV_2026-10-18-07.52.csv

# Write them to a file
bnpfortis2homebank -o homebank_import.csv CSV_2026-10-18-07.52.csv

# Use value dates and overwrite an existing output file
bnpfortis2homebank -v -f -o homebank_import.csv CSV_2026-10-18-07.52.csv
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error (missing or unreadable file, missing columns, output exists, …) |
| 2 | Usage error (no input file, unknown option, …) |

## Importing into HomeBank

1. In HomeBank, choose **File → Import…**.
2. Select the generated CSV file.
3. Set the date format to **y-m-d**.
4. Select the target account and review the transactions before confirming.

Categories and tags are left empty. HomeBank's **automatic assignment rules**
(*Manage → Assignments*) can fill in categories based on payee or memo during
import.

## Column mapping

| HomeBank | Bank export |
|---|---|
| `date` | `Uitvoeringsdatum` (or `Valutadatum` with `-v`) |
| `payment` | `Type verrichting` (see below) |
| `number` | `Volgnummer` |
| `payee` | `Naam van de tegenpartij` |
| `memo` | `Mededeling`, or `Details` when empty |
| `amount` | `Bedrag`, two decimals |
| `category` | *(empty)* |
| `tags` | *(empty)* |

Semicolons inside payee and memo are replaced by commas, since HomeBank's
importer would otherwise split the line.

## Payment type mapping

| Bank transaction type | HomeBank payment |
|---|---|
| Kredietkaartbetaling | 1 – credit card |
| Overschrijving in euro | 4 – bank transfer |
| Instantoverschrijving in euro | 4 – bank transfer |
| Kaartbetaling | 6 – debit card |
| Doorlopende betalingsopdracht | 7 – standing order |
| Kosten in verband met de rekening | 10 – financial institution fee |
| Domiciliëring | 11 – direct debit |
| Hypotheekleningen Terugbetalingen | 11 – direct debit |
| *anything else* | 0 – none (reported as a warning) |

To add or change a mapping, edit the `PAYMENT_MAP` dictionary at the top of
the script.

## Assumptions

- The input is UTF-8, `;`-separated, with dates in `dd/mm/yyyy` format, as in
  the standard BNP Paribas Fortis export.
- Amounts use either a `.` decimal separator (`-1234.50`) or the Belgian
  notation (`-1.234,50`). An empty or unreadable amount becomes `0.00`.
- Refused transactions are recognised by a non-empty `Reden van weigering`
  (reason for refusal) column.

## Tips

Inspect the result before importing:

```bash
column -s ';' -t homebank_import.csv | less -S
```

Count transactions per payment type:

```bash
tail -n +2 homebank_import.csv | cut -d ';' -f 2 | sort -n | uniq -c
```