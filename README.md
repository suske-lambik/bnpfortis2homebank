# bank2homebank

Convert a **BNP Paribas Fortis** CSV export into the CSV import format of
[HomeBank](https://www.gethomebank.org/), the free personal finance manager.

The bank export (Dutch-language) is converted to HomeBank's 8-column format:

```
date;payment;number;payee;memo;amount;category;tags
```

## Features

- Works directly on the file downloaded from the bank. The UTF-8 BOM, spaces
  in column names and Windows line endings are handled automatically.
- Maps the bank's transaction types to HomeBank payment types.
- Converts dates to ISO format (`yyyy-mm-dd`).
- Skips refused transactions by default.
- Uses the message (`Mededeling`) as memo, falling back to `Details` when empty
  (useful for card payments).
- Warns about transaction types it doesn't know yet.

## Requirements

- `bash`, `sed`
- [`q`](https://harelba.github.io/q/) – run SQL directly on CSV files

Install `q` on Debian/Ubuntu from its GitHub release:

```bash
wget https://github.com/harelba/q/releases/download/v3.1.6/q-text-as-data-3.1.6-1.x86_64.deb
sudo dpkg -i q-text-as-data-3.1.6-1.x86_64.deb
```

See the [q installation page](https://harelba.github.io/q/#installation) for
other platforms.

## Installation

```bash
git clone https://github.com/<your-user>/bank2homebank.git
cd bank2homebank
install -m 755 bank2homebank ~/.local/bin/
```

Make sure `~/.local/bin` is in your `PATH`.

## Usage

```
bank2homebank [OPTIONS] INPUT.csv
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
bank2homebank CSV_2026-10-18-07.52.csv

# Write them to a file
bank2homebank -o homebank_import.csv CSV_2026-10-18-07.52.csv

# Use value dates and overwrite an existing output file
bank2homebank -v -f -o homebank_import.csv CSV_2026-10-18-07.52.csv
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Error (missing file, `q` not installed, output exists, …) |
| 2 | No input file given |

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

To add or change a mapping, edit the `case Type_verrichting` block in the
script.

## Assumptions

- The input is `;`-separated with dates in `dd/mm/yyyy` format and amounts
  with a `.` decimal separator, as in the standard BNP Paribas Fortis export.
- Refused transactions are recognised by a non-empty `Reden van weigering`
  (reason for refusal) column.

## Tips

Inspect the result before importing:

```bash
column -s ';' -t homebank_import.csv | less -S
```

Count transactions per payment type:

```bash
q -H -d ';' 'select payment, count(*) from homebank_import.csv group by payment'
```

## Troubleshooting

**`Encoding utf-9-sig could not be found`**
This typo comes from `q`'s own error message. The correct encoding name is
`utf-8-sig`. The script doesn't need it, since it strips the BOM itself.

**`UnicodeEncodeError: 'ascii' codec can't encode …`**
`q` needs a UTF-8 locale. The script switches to `C.UTF-8` automatically when
your locale isn't UTF-8.

**`query error: incomplete input`** (when running your own `q` queries)
`q` puts the query on a single line, so a `--` SQL comment disables
everything after it. Remove the comments.