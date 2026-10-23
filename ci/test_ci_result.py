"""Reject false-positive mutation results and infrastructure failures."""
import unittest
from run_suite import classify


class GateTests(unittest.TestCase):
    def xml(self, body):
        return '<testsuites><testsuite>' + body + '</testsuite></testsuites>'

    def test_normal(self):
        self.assertTrue(classify('normal', 0, self.xml('<testcase name="ok"/>'), ''))

    def test_empty(self):
        self.assertFalse(classify('normal', 0, self.xml(''), ''))

    def test_missing_xml(self):
        self.assertFalse(classify('normal', 0, '', ''))

    def failure(self, message):
        return f'<testcase><failure message="{message}">{message}</failure></testcase>'

    def test_expected_mutations(self):
        from run_suite import CASES
        for mode, family in CASES.items():
            text = family + ': assertion failed'
            case = self.failure(text)
            xml = self.xml(case + case + '<testcase name="passing"/>')
            self.assertTrue(classify(mode, 1, xml, text))
            for code in (0, 2, 3, 4, 5, -9):
                self.assertFalse(classify(mode, code, xml, text))
            self.assertFalse(classify(mode, 1, xml, ''))
            self.assertFalse(classify(mode, 1, xml.replace('message="' + text, 'message="unrelated'), text))

    def test_unrelated_assertion_failure(self):
        self.assertFalse(classify('always-miss', 1, self.xml(self.failure('assert 1 == 2')), 'hit control'))

    def test_collection_error(self):
        xml = self.xml('<testcase><error message="isolation">import failed</error></testcase>')
        self.assertFalse(classify('broken-tenant', 1, xml, 'isolation'))

    def test_zero_failures(self):
        self.assertFalse(classify('always-miss', 1, self.xml('<testcase/>'), 'hit control'))

    def test_mixed_intended_and_unrelated(self):
        for mode, family in [('always-miss', 'hit control'), ('broken-tenant', 'isolation')]:
            xml = self.xml(self.failure(family) + self.failure('unrelated assertion'))
            self.assertFalse(classify(mode, 1, xml, family))
            xml = self.xml(self.failure(family) + '<testcase><error>teardown</error></testcase>')
            self.assertFalse(classify(mode, 1, xml, family))

    def test_timeout_diagnostics(self):
        import contextlib
        import io
        import json
        import subprocess
        from unittest.mock import patch
        import run_suite
        writes = {}
        def save(path, value):
            writes[path.name] = value
        with patch('sys.argv', ['run_suite.py', 'normal']), \
             patch.dict(run_suite.os.environ, {'GITHUB_STEP_SUMMARY': ''}), \
             patch.object(run_suite.Path, 'mkdir'), \
             patch.object(run_suite.Path, 'exists', return_value=False), \
             patch.object(run_suite.Path, 'write_text', save), \
             patch.object(run_suite.subprocess, 'run', side_effect=subprocess.TimeoutExpired(['pytest'], 600, output=b'partial diagnostic')), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(run_suite.main(), 1)
        self.assertEqual(writes['pytest.log'], 'partial diagnostic')
        summary = json.loads(writes['result.json'])
        self.assertFalse(summary['accepted'])
        self.assertEqual(summary['pytest_exit'], 124)
        self.assertEqual(summary['error'], 'pytest timeout')

    def test_skipped(self):
        self.assertFalse(classify('normal', 0, self.xml('<testcase><skipped/></testcase>'), ''))


if __name__ == '__main__':
    unittest.main()
