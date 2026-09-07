# CSV Import Audit

A small, read-only preflight tool for CSV imports. Catch missing required values,
unexpected column counts and duplicate identifiers before importing records into
a CRM or another business system.

An independent portfolio project by Ilya Anisimov, developed with AI assistance.
Includes fictional sample data and automated tests for the documented behavior.

## Run it

Python 3.10 or later is required. There are no external dependencies or API keys.

```sh
python audit_csv.py example.csv --required email --key customer_id
```

Expected output:

```text
CHECK REQUIRED: 4 records, 2 issues.
  Line 4: duplicate_key
  Line 5: missing_required
```

Use a JSON report in an automation pipeline:

```sh
python audit_csv.py example.csv --required email --key customer_id --json
```

Repeat `--required` for additional required columns, or `--key` for a composite
identifier such as account plus external ID. Semicolon-separated exports use
`--delimiter ";"`; tab-separated exports use `--delimiter tab`.

## Behavior contract

| Exit | Meaning |
| --- | --- |
| 0 | The selected checks found no issues |
| 1 | One or more data issues need attention |
| 2 | Invalid input, unreadable file or invalid requested schema |

- Input is opened for reading only. Nothing is uploaded or rewritten.
- UTF-8 with or without BOM, quoted delimiters, CRLF and multiline fields are supported.
- Column names are trimmed and must be nonempty and unique. Matching is case-sensitive.
- Values are trimmed **for comparison only**. Duplicate keys are case-sensitive;
  `ABC` and `abc` are different identifiers. Empty keys are reported separately.
- `line` is the starting physical line of the CSV record. A quoted multiline
  record counts as one record. Blank physical records are skipped and counted.
- A wrong-width record is reported and excluded from value/key checks.
- Reports include column names and locations, but no cell contents. Review column
  names before sharing a report if the schema itself is sensitive.
- The default report retains 1,000 issue details while continuing to count every
  issue. Use `--max-issues` to change this limit, including zero for totals only.
- A file containing only a valid header passes with zero data records; callers
  that require a nonempty import should also check `rows_checked`.

## What this does not validate

It does not verify email deliverability, data types, business rules, whether an ID
already exists in the destination, or whether an import will succeed. A pass means
only that the configured checks passed. It does not repair or deduplicate data.
Non-UTF-8 exports need a separate conversion. Extremely large fields can exceed
Python's CSV parser limit; key tracking uses memory proportional to unique keys.

## Verify

```sh
python -m unittest -v
```

Tests cover the CLI exit/JSON contract, unchanged input, private cell contents,
duplicate and composite identifiers, empty keys, required values, malformed rows,
quoting, BOM, delimiters, multiline locations, encoding and report limits.

## Possible client adaptations

This is a starting point for a scoped data-import task: destination-specific
validation, an approved schema, mapping rules and an automated import gate.
Those additions need the client's acceptance criteria and representative synthetic
examples before implementation.
