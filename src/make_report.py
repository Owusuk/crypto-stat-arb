"""
make_report.py - build the V2 report and methodology explainer (.docx + .pdf)
in two passes so each contents page carries real page numbers.
Pass 1 builds and renders with LibreOffice and finds the page of every
heading; pass 2 rebuilds with those page numbers.
"""
import json
import os
import shutil
import subprocess
import sys

import fitz  # PyMuPDF

SOFFICE = shutil.which("soffice") or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
DOCS = [
    ("src/build_report.py", "crypto_research_report_V2.docx", "data/research/_toc.json", "data/research/_heads.json"),
    ("src/build_explainer.py", "V2_methodology_explainer.docx", "data/research/_toc_explainer.json",
     "data/research/_heads_explainer.json"),
]


def run(builder, toc):
    subprocess.run([sys.executable, builder], check=True, env={**os.environ, "DOC_TOC": toc})


def render(docx):
    subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", ".", docx],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def heading_pages(pdf, heads):
    d = fitz.open(pdf)
    pages, start = [], 2
    for lvl, text in heads:
        found = None
        for i in range(start, len(d)):
            if any(ln.strip().startswith(text[:40]) for ln in d[i].get_text().splitlines()):
                found = i; break
        found = start if found is None else found
        start = found
        pages.append([lvl, text, found + 1])
    return pages


if __name__ == "__main__":
    for builder, docx, toc, heads_f in DOCS:
        pdf = docx.replace(".docx", ".pdf")
        json.dump([[1, "placeholder", 0]], open(toc, "w"))
        run(builder, toc); render(docx)
        heads = json.load(open(heads_f))
        json.dump(heading_pages(pdf, heads), open(toc, "w"))
        run(builder, toc); render(docx)
        check = heading_pages(pdf, heads)
        if check != json.load(open(toc)):
            json.dump(check, open(toc, "w")); run(builder, toc); render(docx)
        os.remove(heads_f)
        print(f"saved {docx} and {pdf}")
