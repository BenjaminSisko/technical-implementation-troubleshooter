from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "scripts"


def run_script(name: str, *arguments: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *(str(value) for value in arguments)],
        check=False,
        capture_output=True,
        text=True,
    )


class ToolTests(unittest.TestCase):
    def test_missing_configuration_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "missing.json"
            checked = run_script("configure_skill.py", "--config", config, "--check-only")
            self.assertNotEqual(checked.returncode, 0)
            self.assertIn("UNCONFIGURED", checked.stderr)
            doctor = run_script("doctor.py", "--config", config)
            self.assertNotEqual(doctor.returncode, 0)
            self.assertIn("NOT_READY", doctor.stdout)

    def test_configuration_preserves_root_label_and_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "corpus"
            root.mkdir()
            (root / "guide.md").write_text("# Guide\n\nBlackwell open module", encoding="utf-8")
            config = base / "config.json"
            index = base / "search.sqlite"
            configured = run_script(
                "configure_skill.py",
                "--root",
                f"nvidia={root}",
                "--config",
                config,
                "--index",
                index,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            payload = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 2)
            self.assertEqual(payload["private_reference_roots"][0]["label"], "nvidia")
            self.assertEqual(config.stat().st_mode & 0o077, 0)
            rebuilt = run_script(
                "configure_skill.py", "--config", config, "--index", index
            )
            self.assertEqual(rebuilt.returncode, 0, rebuilt.stderr)
            payload = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(payload["private_reference_roots"][0]["label"], "nvidia")

    def test_packaged_bundle_index_is_activated_without_rebuild(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            corpus = base / "source"
            corpus.mkdir()
            (corpus / "guide.md").write_text(
                "# Guide\n\nAir-gapped driver guidance", encoding="utf-8"
            )
            bundle = base / "bundle"
            indexes = bundle / "indexes"
            indexes.mkdir(parents=True)
            packaged_index = indexes / "search.sqlite"
            built = run_script(
                "build_private_search_index.py",
                "--root",
                f"vendor={corpus}",
                "--output",
                packaged_index,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            config = base / "config.json"
            activated = run_script(
                "configure_skill.py",
                "--bundle",
                bundle,
                "--config",
                config,
            )
            self.assertEqual(activated.returncode, 0, activated.stderr)
            payload = json.loads(config.read_text(encoding="utf-8"))
            self.assertEqual(payload["private_corpus_bundles"], [str(bundle.resolve())])
            self.assertEqual(
                payload["private_search_indexes"], [str(packaged_index.resolve())]
            )
            doctor = run_script("doctor.py", "--config", config)
            self.assertEqual(doctor.returncode, 0, doctor.stdout + doctor.stderr)
            self.assertIn("READY", doctor.stdout)

    def test_metadata_filter_and_any_term_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "corpus"
            root.mkdir()
            document = root / "driver.md"
            document.write_text(
                "# Driver\n\nBlackwell requires open kernel modules on RHEL.",
                encoding="utf-8",
            )
            digest = hashlib.sha256(document.read_bytes()).hexdigest()
            manifest = base / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "bundle_id": "test",
                        "generated_at": "2026-10-04T00:00:00Z",
                        "documents": [
                            {
                                "path": "driver.md",
                                "sha256": digest,
                                "vendor": "NVIDIA",
                                "product": "Driver",
                                "title": "Open Modules",
                                "version": "580",
                                "platform": "RHEL 9",
                                "os_family": "RHEL",
                                "os_major": "9",
                                "architecture": "x86_64",
                                "hardware_family": "Blackwell",
                                "source_url": "https://example.invalid/driver",
                                "retrieved_at": "2026-10-04T00:00:00Z",
                                "status": "active",
                                "classification": "private",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            index = base / "search.sqlite"
            built = run_script(
                "build_private_search_index.py",
                "--root",
                f"nvidia={root}",
                "--document-manifest",
                f"nvidia={manifest}",
                "--output",
                index,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            searched = run_script(
                "search_private_corpus.py",
                "--index",
                index,
                "--query",
                "Blackwell impossible-term",
                "--vendor",
                "NVIDIA",
                "--status",
                "active",
                "--json",
            )
            self.assertEqual(searched.returncode, 0, searched.stderr)
            payload = json.loads(searched.stdout)
            self.assertEqual(payload["strategy"], "any-term-fallback")
            self.assertEqual(payload["results"][0]["version"], "580")
            self.assertIn("heading-Driver", payload["results"][0]["citation"])

    def test_adjacent_receipt_supplies_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "corpus"
            version = root / "nvidia-guide" / "abc123"
            version.mkdir(parents=True)
            source = version / "source.html"
            source.write_text("<h1>Driver Guide</h1><p>Blackwell open modules</p>", encoding="utf-8")
            (version / "receipt.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "vendor": "NVIDIA",
                        "product": "Driver",
                        "title": "Driver Guide",
                        "canonical_url": "https://example.invalid/driver",
                        "retrieved_at": "2026-10-04T00:00:00Z",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "relative_source_path": "source.html",
                        "classification": "private",
                        "status": "active",
                        "content_type": "text/html",
                    }
                ),
                encoding="utf-8",
            )
            index = base / "search.sqlite"
            built = run_script(
                "build_private_search_index.py",
                "--root",
                f"vendor={root}",
                "--output",
                index,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            searched = run_script(
                "search_private_corpus.py",
                "--index",
                index,
                "--query",
                "Blackwell",
                "--vendor",
                "NVIDIA",
                "--status",
                "active",
                "--json",
            )
            self.assertEqual(searched.returncode, 0, searched.stderr)
            payload = json.loads(searched.stdout)
            self.assertEqual(payload["results"][0]["product"], "Driver")

    def test_sensitive_content_is_quarantined_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "corpus"
            root.mkdir()
            (root / "safe.md").write_text("safe searchable text", encoding="utf-8")
            (root / "incident.md").write_text(
                "-----BEGIN OPENSSH PRIVATE KEY-----\nnot-a-real-key",
                encoding="utf-8",
            )
            index = base / "search.sqlite"
            report = base / "report.json"
            built = run_script(
                "build_private_search_index.py",
                "--root",
                f"case={root}",
                "--output",
                index,
                "--report",
                report,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            payload = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(payload["document_count"], 1)
            self.assertEqual(payload["skipped"]["sensitive_content"], 1)
            self.assertIn(
                {
                    "root_label": "case",
                    "path": "incident.md",
                    "reason": "sensitive_content",
                },
                payload["skip_examples"],
            )

    def test_unsigned_bundle_requires_explicit_exception(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            bundle = base / "bundle"
            bundle.mkdir()
            document = bundle / "guide.txt"
            document.write_text("vendor guidance", encoding="utf-8")
            manifest = bundle / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "bundle_id": "unsigned-test",
                        "generated_at": "2026-10-04T00:00:00Z",
                        "documents": [
                            {
                                "path": "guide.txt",
                                "sha256": hashlib.sha256(document.read_bytes()).hexdigest(),
                                "vendor": "Vendor",
                                "product": "Product",
                                "title": "Guide",
                                "source_url": "https://example.invalid/guide",
                                "retrieved_at": "2026-10-04T00:00:00Z",
                                "status": "active",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            required = run_script(
                "verify_vendor_bundle.py", "--bundle", bundle, "--manifest", manifest
            )
            self.assertNotEqual(required.returncode, 0)
            self.assertIn("signature", required.stderr)
            accepted = run_script(
                "verify_vendor_bundle.py",
                "--bundle",
                bundle,
                "--manifest",
                manifest,
                "--allow-unsigned",
            )
            self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_docx_extraction_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            document = base / "sample.docx"
            with zipfile.ZipFile(document, "w") as archive:
                archive.writestr(
                    "word/document.xml",
                    """<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Driver installation guide</w:t></w:r></w:p></w:body></w:document>""",
                )
            output = base / "sample.md"
            extracted = run_script(
                "extract_document.py", "--input", document, "--output", output
            )
            self.assertEqual(extracted.returncode, 0, extracted.stderr)
            self.assertIn("Driver installation guide", output.read_text(encoding="utf-8"))
            receipt = output.with_suffix(".md.receipt.json")
            self.assertTrue(receipt.is_file())

    def test_dual_harness_links_share_one_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            codex_root = base / ".codex" / "skills"
            claude_root = base / ".claude" / "skills"
            installed = run_script(
                "install_harness_links.py",
                "--source",
                REPO,
                "--codex-root",
                codex_root,
                "--claude-root",
                claude_root,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertEqual(
                (codex_root / "technical-implementation-troubleshooter").resolve(), REPO
            )
            self.assertEqual(
                (claude_root / "technical-implementation-troubleshooter").resolve(), REPO
            )

    def test_doctor_rejects_world_readable_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "corpus"
            root.mkdir()
            (root / "guide.md").write_text("searchable content", encoding="utf-8")
            config = base / "config.json"
            index = base / "search.sqlite"
            configured = run_script(
                "configure_skill.py",
                "--root",
                f"docs={root}",
                "--config",
                config,
                "--index",
                index,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            config.chmod(0o644)
            doctor = run_script("doctor.py", "--config", config)
            self.assertNotEqual(doctor.returncode, 0)
            self.assertIn("NOT_READY", doctor.stdout)
            self.assertIn("configuration-permissions", doctor.stdout)


if __name__ == "__main__":
    unittest.main()
