#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import tomllib
except Exception as exc:  # pragma: no cover
    raise SystemExit(f"tomllib unavailable: {exc}")


def read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def severity_badge(sev: str) -> str:
    cls = "info"
    if sev == "error":
        cls = "error"
    elif sev == "warning":
        cls = "warning"
    return f'<span class="badge {cls}">{sev}</span>'


def findings_table(findings: list[dict[str, Any]]) -> str:
    if not findings:
        return "<p>Không có dữ liệu findings.</p>"
    rows: list[str] = []
    for item in findings:
        rows.append(
            "<tr>"
            f"<td>{item.get('id','')}</td>"
            f"<td>{severity_badge(str(item.get('severity','info')))}</td>"
            f"<td>{item.get('message','')}</td>"
            f"<td><code>{item.get('detail',{})}</code></td>"
            "</tr>"
        )
    return (
        "<table><thead><tr><th>Mã lỗi</th><th>Mức độ</th><th>Mô tả</th><th>Chi tiết</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table>"
    )


def fix_plan_html(batch_fix: dict[str, Any]) -> str:
    if not batch_fix:
        return "<p>Không có batch fix.</p>"
    apply = bool(batch_fix.get("apply", False))
    reason = str(batch_fix.get("reason", ""))
    changes = batch_fix.get("changes", {})
    if not apply:
        return f"<p><strong>Không áp dụng fix.</strong> Lý do: {reason}</p>"
    items = "".join(f"<li><code>{k}</code> = <code>{v}</code></li>" for k, v in changes.items())
    return f"<p><strong>Áp dụng batch fix.</strong> {reason}</p><ul>{items}</ul>"


def render_with_template(template: str, payload: dict[str, str]) -> str:
    out = template
    for key, value in payload.items():
        out = out.replace(key, value)
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Vietnamese HTML report from audit pass TOML.")
    parser.add_argument("--job", required=True, help="Path to job directory")
    parser.add_argument("--pass-index", required=True, type=int, help="Audit pass number")
    args = parser.parse_args()

    job_dir = Path(args.job)
    audit_path = job_dir / "logs" / f"audit_pass_{args.pass_index:02d}.toml"
    template_path = Path(__file__).resolve().parents[1] / "templates" / "audit_report_vi.html"
    if not audit_path.exists():
        raise SystemExit(f"missing audit pass file: {audit_path}")
    if not template_path.exists():
        raise SystemExit(f"missing HTML template: {template_path}")

    data = read_toml(audit_path)
    metadata = data.get("metadata", {})
    findings = data.get("findings", [])
    batch_fix = data.get("batch_fix", {})

    html = render_with_template(
        template_path.read_text(encoding="utf-8"),
        {
            "__TITLE__": f"Audit pass {args.pass_index:02d} - {metadata.get('job_id', job_dir.name)}",
            "__JOB_ID__": str(metadata.get("job_id", job_dir.name)),
            "__PASS_INDEX__": str(metadata.get("pass_index", args.pass_index)),
            "__MAX_PASSES__": str(metadata.get("max_passes", 3)),
            "__PASS_STATUS__": str(metadata.get("pass_status", "unknown")),
            "__GENERATED_AT__": str(metadata.get("generated_at", datetime.now(timezone.utc).isoformat())),
            "__SUMMARY_TEXT__": "Pass này đã gom toàn bộ findings trước khi quyết định batch fix một thể.",
            "__FINDINGS_TABLE__": findings_table(findings if isinstance(findings, list) else []),
            "__FIX_PLAN__": fix_plan_html(batch_fix if isinstance(batch_fix, dict) else {}),
        },
    )

    out_path = job_dir / "logs" / f"audit_report_vi_pass_{args.pass_index:02d}.html"
    out_path.write_text(html, encoding="utf-8")
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
