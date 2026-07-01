"""Parse the DISA SRG-STIG Library (XCCDF 1.1) and validate every benchmark
against :class:`Stig`.

This is an integration test of the STIG catalog models against real-world DISA
content. The library is distributed as a directory of ZIP files, each containing
one or more ``*-xccdf.xml`` benchmark files. The harness also accepts a single
``*.zip``, a loose ``*-xccdf.xml`` file, or a directory containing loose XML.

Run::

    python scripts/import_stig_library.py U_SRG-STIG_Library_April_2026

Exits non-zero if any file fails validation or fails to load, printing a summary
grouped by the first validation error cause so model/parse gaps surface quickly.

Pass ``--out`` to also persist each validated benchmark as canonical JSON plus a
``catalog_manifest.json`` index::

    python scripts/import_stig_library.py U_SRG-STIG_Library_April_2026 --out

The default output location (``stig_catalog/`` at the repo root) is local and
gitignored.

**Portability:** This script uses only the Python standard library for parsing
(``zipfile``, ``xml.etree.ElementTree``, ``html``, ``json``, ``argparse``,
``pathlib``). No third-party XML libraries.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import ValidationError

# Ensure the package is importable when run as a plain script from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from network_models.stig.catalog import Stig  # noqa: E402

# Repo root and the default local (gitignored) destination for converted output.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_OUT = _REPO_ROOT / "stig_catalog"

# XCCDF 1.1 namespace
_NS = "{http://checklists.nist.gov/xccdf/1.1}"


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def collect_xccdf(source: Path) -> list[tuple[str, bytes]]:
    """Collect (source_file, xml_bytes) pairs from the given path.

    Accepts:
      - A directory containing ZIPs (and/or loose *-xccdf.xml files)
      - A single *.zip file
      - A single loose *-xccdf.xml file
    """
    docs: list[tuple[str, bytes]] = []

    if source.is_file():
        if source.suffix == ".zip":
            docs.extend(_read_xccdf_from_zip(source))
        elif source.name.endswith("-xccdf.xml"):
            docs.append((source.name, source.read_bytes()))
        else:
            # Try treating it as a zip anyway
            docs.extend(_read_xccdf_from_zip(source))
        return docs

    if source.is_dir():
        # Process all ZIPs in the directory
        for zp in sorted(source.glob("*.zip")):
            docs.extend(_read_xccdf_from_zip(zp))
        # Also sweep any loose *-xccdf.xml files directly under the directory
        for xml_path in sorted(source.glob("*-xccdf.xml")):
            docs.append((xml_path.name, xml_path.read_bytes()))
        return docs

    return docs


def _read_xccdf_from_zip(zip_path: Path) -> list[tuple[str, bytes]]:
    """Read all *-xccdf.xml members from a ZIP, using the zip name as source."""
    docs: list[tuple[str, bytes]] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                if member.endswith("-xccdf.xml"):
                    docs.append((zip_path.name, zf.read(member)))
    except (zipfile.BadZipFile, OSError):
        # Will be reported as a load error by the caller
        pass
    return docs


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def _text(el: "ET.Element | None") -> str | None:
    """Extract text content from an element, or None if absent/empty."""
    if el is None:
        return None
    return el.text if el.text else None


def _extract_vuln_discussion(raw_description: str | None) -> str | None:
    """Best-effort extraction of <VulnDiscussion> text from XCCDF description.

    XCCDF <description> is HTML-escaped and wraps the useful text inside
    <VulnDiscussion>...</VulnDiscussion>. Falls back to the raw (unescaped)
    description text if the tag isn't present.
    """
    if not raw_description:
        return None
    unescaped = html.unescape(raw_description)
    start_tag = "<VulnDiscussion>"
    end_tag = "</VulnDiscussion>"
    start_idx = unescaped.find(start_tag)
    if start_idx != -1:
        end_idx = unescaped.find(end_tag, start_idx)
        if end_idx != -1:
            return unescaped[start_idx + len(start_tag):end_idx].strip() or None
    # Fallback: return raw unescaped text
    return unescaped.strip() or None


def _classify_type(benchmark_id: str, title: str, source_file: str) -> str:
    """Classify a benchmark as 'srg' or 'stig' by convention.

    DISA naming: SRGs contain 'SRG' or 'Security Requirements Guide' in
    their identifiers/titles/filenames. Everything else is a STIG.
    """
    hay = f"{benchmark_id} {title} {source_file}".lower()
    if "srg" in hay or "security requirements guide" in hay:
        return "srg"
    return "stig"


def parse_benchmark(xml_bytes: bytes, source_file: str) -> dict[str, Any]:
    """Parse XCCDF 1.1 benchmark XML into kwargs suitable for Stig(**kwargs).

    Raises ET.ParseError on malformed XML.
    """
    root = ET.fromstring(xml_bytes)
    ns = _NS

    benchmark_id = root.get("id", "")
    title_el = root.find(f"{ns}title")
    title = _text(title_el) or benchmark_id
    version_el = root.find(f"{ns}version")
    version = _text(version_el) or "0"

    # Status
    status_el = root.find(f"{ns}status")
    status = _text(status_el)
    status_date_str = status_el.get("date") if status_el is not None else None
    status_date = None
    if status_date_str:
        try:
            status_date = date.fromisoformat(status_date_str)
        except ValueError:
            pass

    # Release info from <plain-text id="release-info">
    release_info = None
    for pt in root.findall(f"{ns}plain-text"):
        if pt.get("id") == "release-info":
            release_info = _text(pt)
            break

    # Type classification
    stig_type = _classify_type(benchmark_id, title, source_file)

    # --- Rules (Groups) ---
    rules: list[dict[str, Any]] = []
    group_to_rule: dict[str, str] = {}

    for group in root.findall(f"{ns}Group"):
        group_id = group.get("id", "")
        rule_el = group.find(f"{ns}Rule")
        if rule_el is None:
            continue

        rule_id = rule_el.get("id", "")
        group_to_rule[group_id] = rule_id

        # severity: verbatim from @severity, default "unknown"
        severity = rule_el.get("severity") or "unknown"

        # weight
        weight_str = rule_el.get("weight")
        weight: float | None = None
        if weight_str:
            try:
                weight = float(weight_str)
            except ValueError:
                pass

        # title
        rule_title = _text(rule_el.find(f"{ns}title")) or ""

        # stig_id (from Rule/<version>)
        stig_id = _text(rule_el.find(f"{ns}version"))

        # description -> discussion
        raw_desc = _text(rule_el.find(f"{ns}description"))
        discussion = _extract_vuln_discussion(raw_desc)

        # check
        check_el = rule_el.find(f"{ns}check")
        check_content: str | None = None
        check_content_ref: str | None = None
        check_system: str | None = None
        if check_el is not None:
            check_system = check_el.get("system")
            cc_el = check_el.find(f"{ns}check-content")
            check_content = _text(cc_el)
            ccr_el = check_el.find(f"{ns}check-content-ref")
            if ccr_el is not None:
                check_content_ref = ccr_el.get("name") or ccr_el.get("href")

        # fix / fixtext
        fix_el = rule_el.find(f"{ns}fix")
        fixtext_el = rule_el.find(f"{ns}fixtext")
        fix_text = _text(fixtext_el)
        fix_id: str | None = None
        if fix_el is not None:
            fix_id = fix_el.get("id")
        if not fix_id and fixtext_el is not None:
            fix_id = fixtext_el.get("fixref")

        # idents -> ccis and legacy_ids
        ccis: list[str] = []
        legacy_ids: list[str] = []
        for ident in rule_el.findall(f"{ns}ident"):
            system = ident.get("system") or ""
            ident_text = ident.text or ""
            if not ident_text:
                continue
            if system.endswith("/cci"):
                if ident_text not in ccis:
                    ccis.append(ident_text)
            elif system.endswith("/legacy"):
                if ident_text not in legacy_ids:
                    legacy_ids.append(ident_text)

        rules.append({
            "group_id": group_id,
            "rule_id": rule_id,
            "stig_id": stig_id,
            "severity": severity,
            "weight": weight,
            "title": rule_title,
            "discussion": discussion,
            "check_content": check_content,
            "check_content_ref": check_content_ref,
            "check_system": check_system,
            "fix_text": fix_text,
            "fix_id": fix_id,
            "ccis": ccis,
            "legacy_ids": legacy_ids,
        })

    # --- Profiles ---
    profiles: list[dict[str, Any]] = []
    for profile_el in root.findall(f"{ns}Profile"):
        profile_id = profile_el.get("id", "")
        profile_title = _text(profile_el.find(f"{ns}title"))
        # Collect selected rule references (XCCDF <select idref> points at Group ids)
        selected_group_ids: list[str] = []
        for sel in profile_el.findall(f"{ns}select"):
            if sel.get("selected") == "true":
                idref = sel.get("idref", "")
                if idref:
                    selected_group_ids.append(idref)

        # Remap from Group V-ids to Rule ids
        selected_rule_ids: list[str] = []
        seen_rule_ids: set[str] = set()
        for gid in selected_group_ids:
            rid = group_to_rule.get(gid, gid)
            if rid not in seen_rule_ids:
                selected_rule_ids.append(rid)
                seen_rule_ids.add(rid)

        profiles.append({
            "id": profile_id,
            "title": profile_title,
            "selected_rule_ids": selected_rule_ids,
        })

    return {
        "benchmark_id": benchmark_id,
        "title": title,
        "version": version,
        "release_info": release_info,
        "status": status,
        "status_date": status_date,
        "type": stig_type,
        "source_file": source_file,
        "profiles": profiles,
        "rules": rules,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _first_error_key(exc: ValidationError) -> str:
    """A compact grouping key for the first validation error in *exc*."""
    err = exc.errors()[0]
    loc = ".".join(str(p) for p in err["loc"] if not isinstance(p, int))
    return f"{loc or '<root>'}: {err['type']}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse the DISA SRG-STIG Library and validate against Stig models."
    )
    parser.add_argument(
        "library",
        type=Path,
        help="Path to the DISA SRG-STIG Library directory, a single .zip, or a loose *-xccdf.xml file.",
    )
    parser.add_argument(
        "--max-examples",
        type=int,
        default=8,
        help="Max example failures to print per error group",
    )
    parser.add_argument(
        "--out",
        type=Path,
        nargs="?",
        const=_DEFAULT_OUT,
        default=None,
        metavar="DIR",
        help=(
            "Persist each validated benchmark as canonical JSON under DIR, "
            f"plus a catalog_manifest.json index (default: {_DEFAULT_OUT} when "
            "the flag is given without a value)."
        ),
    )
    args = parser.parse_args()

    source: Path = args.library
    if not source.exists():
        print(f"error: {source} not found", file=sys.stderr)
        return 2

    # Collect XCCDF documents
    xccdf_docs = collect_xccdf(source)
    if not xccdf_docs:
        print(f"error: no *-xccdf.xml content found in {source}", file=sys.stderr)
        return 2

    out_dir: Path | None = args.out
    if out_dir is not None:
        out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    ok = 0
    written = 0
    failures: dict[str, list[tuple[str, str]]] = {}
    load_errors: list[tuple[str, str]] = []
    manifest: list[dict[str, Any]] = []

    for source_file, xml_bytes in xccdf_docs:
        total += 1
        # Parse
        try:
            kwargs = parse_benchmark(xml_bytes, source_file)
        except ET.ParseError as e:
            load_errors.append((source_file, f"XML parse error: {e}"))
            continue
        except Exception as e:
            load_errors.append((source_file, f"Parse error: {type(e).__name__}: {e}"))
            continue

        # Validate against the Stig model
        try:
            stig = Stig(**kwargs)
            ok += 1
        except ValidationError as exc:
            key = _first_error_key(exc)
            msg = exc.errors()[0]["msg"]
            failures.setdefault(key, []).append((source_file, msg))
            continue
        except Exception as exc:
            failures.setdefault(f"<{type(exc).__name__}>", []).append(
                (source_file, str(exc))
            )
            continue

        # Persist JSON if --out
        if out_dir is not None:
            filename = f"{stig.benchmark_id}_{stig.version}.json"
            dest = out_dir / filename
            dest.write_text(
                stig.model_dump_json(indent=2) + "\n",
                encoding="utf-8",
            )
            written += 1
            manifest.append({
                "benchmark_id": stig.benchmark_id,
                "version": stig.version,
                "type": str(stig.type),
                "title": stig.title,
                "rule_count": len(stig.rules),
                "source_file": stig.source_file,
            })

    # Write catalog manifest
    if out_dir is not None and manifest:
        manifest.sort(key=lambda m: (m["benchmark_id"], m["version"]))
        (out_dir / "catalog_manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    # Summary
    failed = total - ok - len(load_errors)
    print("=" * 72)
    print(f"Benchmarks processed   : {total}")
    print(f"  passed               : {ok}")
    print(f"  failed (validation)  : {failed}")
    if load_errors:
        print(f"  failed (load/parse)  : {len(load_errors)}")
    if out_dir is not None:
        print(f"  written to {out_dir} : {written} (+ catalog_manifest.json)")
    print("=" * 72)

    if failures:
        print("\nFailures grouped by first validation error:\n")
        for key in sorted(failures, key=lambda k: len(failures[k]), reverse=True):
            items = failures[key]
            print(f"[{len(items):>4}]  {key}")
            for src, msg in items[: args.max_examples]:
                print(f"           - {src}\n             {msg}")
            if len(items) > args.max_examples:
                print(f"           ... and {len(items) - args.max_examples} more")
            print()

    if load_errors:
        print("Load/parse errors:")
        for src, msg in load_errors[: args.max_examples]:
            print(f"  - {src}: {msg}")
        if len(load_errors) > args.max_examples:
            print(f"  ... and {len(load_errors) - args.max_examples} more")

    has_failures = failed > 0 or len(load_errors) > 0
    return 0 if not has_failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
