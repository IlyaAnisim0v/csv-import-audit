"""Behavior and command-line regression tests; no third-party packages."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from audit_csv import AuditError, audit_csv


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "input.csv"

    def write(self, content):
        self.path.write_bytes(content.encode("utf-8"))

    def test_clean_file_is_unchanged(self):
        self.write('id,name\r\n1,"Example, Inc."\r\n2,Other\r\n')
        original = self.path.read_bytes()
        report = audit_csv(self.path, required=("name",), key=("id",))
        self.assertTrue(report["ok"])
        self.assertEqual(report["rows_checked"], 2)
        self.assertEqual(self.path.read_bytes(), original)

    def test_required_duplicate_and_wrong_width(self):
        self.write("id,name\n1,A\n1, \n2,B,extra\n")
        report = audit_csv(self.path, required=("name",), key=("id",))
        self.assertEqual([i["code"] for i in report["issues"]],
                         ["missing_required", "duplicate_key", "column_count"])
        self.assertEqual(report["issues"][1]["first_line"], 2)
        self.assertEqual(report["rows_checked"], 3)

    def test_bom_semicolon_and_trimmed_header(self):
        self.write("\ufeff id ;name\n1;Example\n")
        self.assertTrue(audit_csv(self.path, delimiter=";", key=("id",))["ok"])

    def test_multiline_locations_and_blank_lines(self):
        self.write('id,note\n1,"two\nlines"\n\n1,next\n')
        report = audit_csv(self.path, key=("id",))
        self.assertEqual(report["blank_records_skipped"], 1)
        self.assertEqual(report["issues"][0]["line"], 5)
        self.assertEqual(report["issues"][0]["first_line"], 2)

    def test_blank_keys_are_not_collapsed_into_duplicates(self):
        self.write("id,name\n,A\n ,B\n")
        report = audit_csv(self.path, key=("id",))
        self.assertEqual([i["code"] for i in report["issues"]], ["empty_key", "empty_key"])

    def test_composite_key_preserves_case_and_trims_spaces(self):
        self.write("account,id\nA,1\nB,1\na,1\n A , 1 \n")
        report = audit_csv(self.path, key=("account", "id"))
        self.assertEqual(report["issue_count"], 1)
        self.assertEqual(report["issues"][0]["line"], 5)

    def test_detail_limit_does_not_hide_total_or_failure(self):
        self.write("id\n1\n1\n1\n")
        report = audit_csv(self.path, key=("id",), max_issues=0)
        self.assertFalse(report["ok"])
        self.assertEqual(report["issue_count"], 2)
        self.assertEqual(report["issues_truncated"], 2)
        self.assertEqual(report["issues"], [])

    def test_report_omits_cell_contents(self):
        self.write("id,name\nprivate-key,private-name\nprivate-key,other-name\n")
        report = json.dumps(audit_csv(self.path, key=("id",)))
        for secret in ("private-key", "private-name", "other-name"):
            self.assertNotIn(secret, report)

    def test_invalid_headers_and_quotes_are_errors(self):
        for content in ("", "\n", "id,\n1,A\n", "id, id \n1,A\n", 'id,note\n1,"unfinished'):
            with self.subTest(content=content):
                self.write(content)
                with self.assertRaises(AuditError):
                    audit_csv(self.path)

    def test_missing_requested_column_is_error(self):
        self.write("id\n1\n")
        with self.assertRaises(AuditError):
            audit_csv(self.path, required=("email",))

    def test_header_only_file_is_valid(self):
        self.write("id,name\n")
        report = audit_csv(self.path)
        self.assertTrue(report["ok"])
        self.assertEqual(report["rows_checked"], 0)

    def test_invalid_encoding_and_missing_file_are_errors(self):
        self.path.write_bytes(b"name\n\xff\n")
        with self.assertRaises(AuditError):
            audit_csv(self.path)
        self.path.unlink()
        with self.assertRaises(AuditError):
            audit_csv(self.path)

    def test_cli_exit_codes_and_json(self):
        script = Path(__file__).with_name("audit_csv.py")
        for content, expected in (("id\n1\n", 0), ("id\n1\n1\n", 1), ("other\n1\n", 2)):
            with self.subTest(expected=expected):
                self.write(content)
                result = subprocess.run(
                    [sys.executable, str(script), str(self.path), "--key", "id", "--json"],
                    text=True, capture_output=True, check=False,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(json.loads(result.stdout)["ok"], expected == 0)
                self.assertEqual(result.stderr, "")

    def test_tab_delimiter(self):
        self.write("id\tname\n1\tExample\n")
        self.assertTrue(audit_csv(self.path, delimiter="\t", key=("id",))["ok"])

    def test_invalid_options(self):
        self.write("id\n1\n")
        for options in ({"delimiter": "::"}, {"delimiter": "\n"}, {"max_issues": -1}):
            with self.subTest(options=options):
                with self.assertRaises(AuditError):
                    audit_csv(self.path, **options)


if __name__ == "__main__":
    unittest.main()
