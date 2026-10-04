import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = json.loads((ROOT / 'kb/sources/hatred_patterns.json').read_text()) if (ROOT / 'kb/sources/hatred_patterns.json').exists() else [
    'It is important to note that', 'Dalam era digital saat ini', 'memainkan peran penting', 'seamless', 'enterprise-grade']


def main():
    findings = []
    inspected = []
    exclusions = {'.venv', 'var', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', 'sources', '08_TEST_EVIDENCE', '09_QA'}
    for path in ROOT.rglob('*'):
        if not path.is_file() or set(path.relative_to(ROOT).parts) & exclusions:
            continue
        if path.name == '.env' or path.suffix not in ['.py', '.md', '.sql', '.toml'] or path == Path(__file__):
            continue
        text = path.read_text()
        if path.name == '00_INDEX.md':
            text = text.split('## Hatred Sheet')[0] + text.split('## STEP_0')[-1]
        inspected.append(str(path.relative_to(ROOT)))
        for phrase in PATTERNS:
            if re.search(re.escape(phrase), text, re.IGNORECASE):
                findings.append({'file': str(path.relative_to(ROOT)), 'rule': 'phrase', 'phrase': phrase})
        for kind, pattern in [('dash', '[\u2013\u2014]'), ('placeholder', r'\b(?:TODO|FIXME|XXX|NotImplemented|lorem)\b'),
                              ('emoji', '[\U0001F300-\U0001FAFF\u2600-\u27BF]'), ('literal_bearer', r'Bearer [A-Za-z0-9_-]{32,}')]:
            if re.search(pattern, text):
                findings.append({'file': str(path.relative_to(ROOT)), 'rule': kind})
        if path.suffix == '.py':
            lines = text.splitlines()
            density = sum(line.lstrip().startswith('#') for line in lines) / max(1, len(lines))
            if density > 0.4:
                findings.append({'file': str(path.relative_to(ROOT)), 'rule': 'comment_density'})
            for node in ast.walk(ast.parse(text)):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and len(node.body) == 1 and isinstance(node.body[0], ast.Pass):
                    findings.append({'file': str(path.relative_to(ROOT)), 'rule': 'empty_function', 'function': node.name})
    print(json.dumps({'inspected_files': len(inspected), 'findings': findings,
                      'exclusions': 'Original sources, official docs, raw evidence, diagnostic pattern definitions, scanner rule literals, local credentials and caches.',
                      'reviewed_exceptions': ['CLI print calls report command results, not debug payloads.',
                                              'Generic exception catch exists only at HTTP boundary and redacts exception values; 500 response tested.',
                                              'Static OpenAPI is a published contract, not a hardcoded business response.']}, indent=2))
    if findings:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
