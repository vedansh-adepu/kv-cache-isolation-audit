"""Run the full CPU suite and accept only intended mutation failure families."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

CASES = {
    'always-miss': 'hit control',
    'broken-tenant': 'isolation',
}


def classify(mode, code, xml, log):
    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return False
    cases = root.findall('.//testcase')
    if not cases or root.findall('.//error') or root.findall('.//skipped'):
        return False
    failures = root.findall('.//failure')
    if mode == 'normal':
        return code == 0 and not failures
    family = CASES[mode]
    return (code == 1 and bool(failures) and family in log
            and all(family in failure.get('message', '') for failure in failures))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['normal', *CASES])
    parser.add_argument('--output', type=Path, default=Path('ci-results'))
    args = parser.parse_args()
    destination = args.output / args.mode
    destination.mkdir(parents=True, exist_ok=False)
    xml = destination / 'pytest.xml'
    env = dict(os.environ, CACHE_AUDIT_MUTATION='none' if args.mode == 'normal' else args.mode)
    error = None
    try:
        result = subprocess.run([sys.executable, '-B', '-m', 'pytest', 'tests', '-q', '-ra',
                                 '--junitxml=' + str(xml)], env=env, text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=600)
        code, output = result.returncode, result.stdout
    except subprocess.TimeoutExpired as failure:
        code, output, error = 124, failure.output or '', 'pytest timeout'
        if isinstance(output, bytes):
            output = output.decode('utf-8', errors='replace')
    (destination / 'pytest.log').write_text(output)
    xml_text = xml.read_text() if xml.exists() else ''
    accepted = classify(args.mode, code, xml_text, output)
    try:
        root = ET.fromstring(xml_text)
        failures, errors = len(root.findall('.//failure')), len(root.findall('.//error'))
    except ET.ParseError:
        failures, errors = None, None
    kills = failures if accepted and args.mode != 'normal' else 0
    summary = {'mode': args.mode, 'pytest_exit': code, 'accepted': accepted, 'error': error,
               'failures': failures, 'errors': errors, 'intended_kills': kills}
    (destination / 'result.json').write_text(json.dumps(summary, indent=2) + '\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as stream:
            stream.write(f"### {args.mode}\nAccepted: {accepted}; intended kills: {kills}; "
                         f"failures: {failures}; errors: {errors}; pytest exit: {code}\n")
    print(output)
    print(json.dumps(summary))
    return 0 if accepted else 1


if __name__ == '__main__':
    sys.exit(main())
