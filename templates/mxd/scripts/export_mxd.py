# -*- coding: utf-8 -*-
"""Py2/ArcPy script called by core.arcgis_bridge.

The Python 3 bridge passes the JSON control file through NEXOMAP_JOB_JSON to
avoid non-ASCII argv problems on ArcMap Python 2.7.
"""
from __future__ import print_function

import json
import os
import shutil
import sys


def main():
    job_path = os.environ.get("NEXOMAP_JOB_JSON")
    if not job_path or not os.path.exists(job_path):
        print("NEXOMAP_JOB_JSON ausente ou inexistente", file=sys.stderr)
        return 2
    with open(job_path, "rb") as f:
        job = json.loads(f.read().decode("utf-8"))

    try:
        import arcpy  # noqa
    except Exception as e:
        print("ArcPy indisponivel: %s" % e, file=sys.stderr)
        return 3

    template = job["template_mxd"]
    out_mxd = job["output_mxd"]
    out_pdf = job.get("output_pdf")
    if not os.path.exists(template):
        print("template MXD nao encontrado: %s" % template, file=sys.stderr)
        return 4

    out_dir = os.path.dirname(out_mxd)
    if out_dir and not os.path.isdir(out_dir):
        os.makedirs(out_dir)

    shutil.copy2(template, out_mxd)
    mxd = arcpy.mapping.MapDocument(out_mxd)
    spec = job.get("mapspec") or {}
    for elm in arcpy.mapping.ListLayoutElements(mxd, "TEXT_ELEMENT"):
        name = (getattr(elm, "name", "") or "").lower()
        if name in ("titulo", "title") or "titulo" in name:
            elm.text = spec.get("titulo", elm.text)
        if "metadado" in name:
            elm.text = "NexoMap AI"
    mxd.save()
    if out_pdf:
        arcpy.mapping.ExportToPDF(mxd, out_pdf, resolution=150)
    del mxd
    if not os.path.exists(out_mxd):
        print("MXD nao foi criado", file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
