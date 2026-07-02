# -*- coding: utf-8 -*-
"""ArcMap/ArcPy bridge for real MXD generation.

The bridge is intentionally conservative: it only reports success when ArcMap,
the template and the on-disk output all exist. It does not fake MXD files.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass

from core.nexomap_catalog import template_index
from core.nexomap_project import NexoMapError, NexoMapProject


DEFAULT_ARCGIS_PYTHON = r"C:\Python27\ArcGIS10.8\python.exe"


class ArcGISBridgeError(NexoMapError):
    pass


@dataclass
class ArcGISDoctor:
    python_path: str
    python_exists: bool
    manifest_exists: bool
    available: bool
    message: str

    def to_dict(self) -> dict:
        return {
            "python_path": self.python_path,
            "python_exists": self.python_exists,
            "manifest_exists": self.manifest_exists,
            "available": self.available,
            "message": self.message,
        }


def arcgis_python_path(secrets: dict | None = None) -> str:
    return (secrets or {}).get("arcgis_python") or os.environ.get("NEXOMAP_ARCGIS_PYTHON") or DEFAULT_ARCGIS_PYTHON


def doctor(project: NexoMapProject | None = None, secrets: dict | None = None) -> ArcGISDoctor:
    py = arcgis_python_path(secrets)
    py_exists = os.path.exists(py)
    manifest_exists = os.path.exists(project.template_manifest_path()) if project else False
    available = py_exists and (manifest_exists if project else True)
    if available:
        msg = "ArcGIS bridge pronto para executar templates MXD."
    elif not py_exists:
        msg = "ArcMap Python 2.7 nao encontrado. Configure arcgis_python em secrets.local.json."
    else:
        msg = "Manifesto de templates MXD nao encontrado."
    return ArcGISDoctor(py, py_exists, manifest_exists, available, msg)


def export_mxd(project: NexoMapProject, spec: dict, manifest: dict, job_dir: str,
               secrets: dict | None = None, timeout: int = 240) -> str:
    templates = template_index(manifest)
    template = templates.get(spec.get("layout_template"))
    if not template:
        raise ArcGISBridgeError(f"template MXD inexistente: {spec.get('layout_template')}")
    template_path = template.get("mxd")
    if not template_path:
        raise ArcGISBridgeError(f"template {template['id']} nao define arquivo .mxd")
    template_abs = project.resolve_repo_or_data_path(template_path)
    if not os.path.exists(template_abs):
        raise ArcGISBridgeError(f"arquivo MXD template nao encontrado: {template_abs}")

    py = arcgis_python_path(secrets)
    if not os.path.exists(py):
        raise ArcGISBridgeError(f"ArcMap Python nao encontrado: {py}")

    os.makedirs(job_dir, exist_ok=True)
    out_mxd = os.path.join(job_dir, "mapa.mxd")
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "mxd", "scripts", "export_mxd.py")
    if not os.path.exists(script):
        raise ArcGISBridgeError(f"script ArcPy nao encontrado: {script}")

    payload = {
        "template_mxd": template_abs,
        "output_mxd": out_mxd,
        "output_pdf": os.path.join(job_dir, "mapa_arcgis.pdf"),
        "project": project._arquivo,
        "mapspec": spec,
    }
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
        control_path = f.name
    env = os.environ.copy()
    env["NEXOMAP_JOB_JSON"] = control_path
    try:
        result = subprocess.run([py, script], env=env, cwd=job_dir, capture_output=True, text=True, timeout=timeout)
    finally:
        try:
            os.remove(control_path)
        except OSError:
            pass

    if result.returncode != 0:
        raise ArcGISBridgeError((result.stderr or result.stdout or f"ArcPy saiu com codigo {result.returncode}")[:1000])
    if not os.path.exists(out_mxd):
        raise ArcGISBridgeError("ArcPy terminou sem criar mapa.mxd")
    return out_mxd
