"""Proof-envelope controls with explicitly synthetic, mocked source checks."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import m30_natural_evidence as evidence
from m30_natural_sources import SourceError


def test_dirty_worktree_refuses_capture(monkeypatch, tmp_path):
    monkeypatch.setattr(evidence.subprocess, 'check_output', lambda *a, **kw: ' M scripts/example.py\n')
    with pytest.raises(SourceError, match='clean committed'):
        evidence.clean(tmp_path)


@pytest.fixture
def envelope(tmp_path, monkeypatch):
    bundle = tmp_path / 'runs/evidence/M30/synthetic'
    bundle.mkdir(parents=True)
    raw = b'original synthetic observation'
    (bundle / 'observation.json').write_bytes(raw)
    (bundle / 'raw-capture-receipt.json').write_text(json.dumps({'artifacts': [
        {'path': 'observation.json', 'sha256': hashlib.sha256(raw).hexdigest()}]}))
    audit = {'configuration_fingerprint': 'sha256:' + 'b' * 64,
             'runtime': {'runtime_revision': 'a' * 40}, 'captured_at': '2026-09-22T00:00:00+00:00'}
    monkeypatch.setattr(evidence, 'clean', lambda root: None)
    monkeypatch.setattr(evidence, 'revision', lambda root: 'c' * 40)
    monkeypatch.setattr(evidence, 'check_sources', lambda *args: audit)
    monkeypatch.setattr(evidence.subprocess, 'check_output', lambda *a, **kw: b'{"synthetic":true}')
    def run(argv, **kwargs):
        output = b'10 passed\n' if 'pytest' in argv else b'milestone governance valid\n'
        return subprocess.CompletedProcess(argv, 0, output)
    monkeypatch.setattr(evidence.subprocess, 'run', run)
    evidence.finalize(bundle, tmp_path)
    return bundle, tmp_path


def test_synthetic_envelope_round_trip(envelope):
    bundle, root = envelope
    evidence.verify(bundle, root)


@pytest.mark.parametrize('field,value', [('runtime_revision', 'wrong'), ('git_revision', 'wrong'),
                                       ('dirty_worktree', True), ('exit_code', True), ('operation', 'other')])
def test_envelope_mismatch_refused(envelope, field, value):
    bundle, root = envelope
    manifest = json.loads((bundle / 'manifest.json').read_text())
    manifest[field] = value
    (bundle / 'manifest.json').write_text(json.dumps(manifest))
    with pytest.raises(SourceError):
        evidence.verify(bundle, root)


def test_no_overwrite_derived_files(envelope):
    bundle, root = envelope
    original = (bundle / 'manifest.json').read_bytes()
    with pytest.raises(SourceError, match='already exist'):
        evidence.finalize(bundle, root)
    assert (bundle / 'manifest.json').read_bytes() == original


def test_manifest_symlink_rejected(envelope):
    bundle, root = envelope
    original = bundle / 'manifest.json'
    original.rename(bundle / 'saved-manifest.json')
    original.symlink_to(bundle / 'saved-manifest.json')
    with pytest.raises(SourceError, match='unsafe manifest'):
        evidence.verify(bundle, root)


def test_inventory_tampering_rejected(envelope):
    bundle, root = envelope
    (bundle / 'observation.json').write_bytes(b'changed')
    with pytest.raises(SourceError, match='hash mismatch'):
        evidence.verify(bundle, root)


def test_verify_rejects_dirty_code(envelope, monkeypatch):
    bundle, root = envelope
    def dirty(root):
        raise SourceError('dirty code')
    monkeypatch.setattr(evidence, 'clean', dirty)
    with pytest.raises(SourceError, match='dirty code'):
        evidence.verify(bundle, root)


def test_legacy_entrypoint_routes_natural_manifest(envelope, monkeypatch):
    import m30_evidence_contract as legacy
    bundle, root = envelope
    calls = []
    monkeypatch.setattr(evidence, 'verify', lambda b, r: calls.append((b, r)))
    legacy.verify(bundle, root)
    assert calls == [(bundle, root)]
