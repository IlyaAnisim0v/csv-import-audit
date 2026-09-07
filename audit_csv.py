"""Read-only CSV preflight checks. Python 3.10+, standard library only."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


class AuditError(ValueError):
    """The input or requested schema cannot be audited."""


def audit_csv(
    path: Path,
    *,
    required: tuple[str, ...] = (),
    key: tuple[str, ...] = (),
    delimiter: str = ",",
    max_issues: int = 1000,
) -> dict:
    """Check shape, required values and repeated keys without changing input.

    Whitespace is stripped only for comparison. Key comparison is case-sensitive.
    Reports contain locations and column names, never cell contents.
    """
    if len(delimiter) != 1 or delimiter in '\r\n"':
        raise AuditError("Delimiter must be one character other than a newline or quote.")
    if max_issues < 0:
        raise AuditError("max_issues must be zero or greater.")
    issues: list[dict] = []
    issue_count = 0
    rows_checked = 0
    blank_records = 0
    seen: dict[tuple[str, ...], int] = {}

    def record(code: str, line: int, **details: object) -> None:
        nonlocal issue_count
        issue_count += 1
        if len(issues) < max_issues:
            issues.append({"code": code, "line": line, **details})

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.reader(source, delimiter=delimiter, strict=True)
            raw_header = next(reader, None)
            if not raw_header:
                raise AuditError("A header row is required.")
            header = [value.strip() for value in raw_header]
            if any(not value for value in header):
                raise AuditError("Column names must not be empty.")
            if len(set(header)) != len(header):
                raise AuditError("Column names must be unique after trimming whitespace.")
            requested = set(required) | set(key)
            if not requested.issubset(header):
                raise AuditError("A requested required/key column is absent from the header.")
            positions = {name: index for index, name in enumerate(header)}
            while True:
                line = reader.line_num + 1
                row = next(reader, None)
                if row is None:
                    break
                if not row:
                    blank_records += 1
                    continue
                rows_checked += 1
                if len(row) != len(header):
                    record("column_count", line, expected=len(header), actual=len(row))
                    continue
                missing = [name for name in dict.fromkeys(required) if not row[positions[name]].strip()]
                if missing:
                    record("missing_required", line, columns=missing)
                if key:
                    identity = tuple(row[positions[name]].strip() for name in key)
                    if all(identity):
                        if identity in seen:
                            record("duplicate_key", line, first_line=seen[identity], columns=list(key))
                        else:
                            seen[identity] = line
                    else:
                        record("empty_key", line, columns=list(key))
    except UnicodeError as exc:
        raise AuditError("Input must be UTF-8 (a UTF-8 BOM is supported).") from exc
    except csv.Error as exc:
        raise AuditError("CSV parsing failed; check quoting, delimiter and oversized fields.") from exc
    except OSError as exc:
        raise AuditError("Input could not be read; check its path and permissions.") from exc

    return {
        "report_version": 1,
        "ok": issue_count == 0,
        "columns_count": len(header),
        "rows_checked": rows_checked,
        "blank_records_skipped": blank_records,
        "issue_count": issue_count,
        "issues_truncated": issue_count - len(issues),
        "issues": issues,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check a CSV before import; never modify its contents.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--required", action="append", default=[], metavar="COLUMN")
    parser.add_argument("--key", action="append", default=[], metavar="COLUMN", help="Repeat for a composite key.")
    parser.add_argument("--delimiter", default=",", help="Comma by default; use ';' for semicolon CSV, 'tab' for TSV.")
    parser.add_argument("--max-issues", type=int, default=1000, help="Maximum detail records; counts remain complete.")
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    try:
        report = audit_csv(
            args.input,
            required=tuple(args.required),
            key=tuple(args.key),
            delimiter="\t" if args.delimiter == "tab" else args.delimiter,
            max_issues=args.max_issues,
        )
    except AuditError as exc:
        if args.json_output:
            print(json.dumps({"report_version": 1, "ok": False, "error": str(exc)}))
        else:
            print(f"Cannot audit: {exc}", file=sys.stderr)
        return 2
    if args.json_output:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        state = "PASS" if report["ok"] else "CHECK REQUIRED"
        print(f"{state}: {report['rows_checked']} records, {report['issue_count']} issues.")
        for issue in report["issues"]:
            print(f"  Line {issue['line']}: {issue['code']}")
        if report["issues_truncated"]:
            print(f"  {report['issues_truncated']} further issue details omitted.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
