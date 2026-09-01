"""Tests informe Fase D (sin red)."""

from mmi.analysis.data_report import build_data_report


def test_build_data_report_minimal(tmp_path):
    status = {
        "summary": {"pass": 10, "reject": 2, "indexados": 8, "total": 12},
        "analyses": [
            {
                "name": "a.pdf",
                "extension": ".pdf",
                "tipo": "norma",
                "status": "pass",
                "relative_path": "ODS1 TORR ENF DCH/00 DOCUMENTOS NCC30/a.pdf",
                "included_in_analysis": True,
                "index_status": "active",
            },
            {
                "name": "b.xlsx",
                "extension": ".xlsx",
                "tipo": "tabla",
                "status": "reject",
                "notes": ["plantilla vacía"],
                "relative_path": "ODS1 TORR ENF DCH/02 INF TEC/b.xlsx",
                "included_in_analysis": True,
            },
        ],
    }
    (tmp_path / "analysis-status.json").write_text(
        __import__("json").dumps(status), encoding="utf-8"
    )
    report = build_data_report(tmp_path)
    assert report["corpus_summary"]["pass"] == 10
    assert report["phase0_by_extension"]["pdf"]["pass"] == 1
    assert report["reject_top"][0]["reason"] == "plantilla vacía"
    assert report["recommendations"]
