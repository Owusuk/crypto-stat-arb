"""
make_report.py - build crypto_research_report.docx and its PDF in two passes so
the contents page carries real page numbers.

Pass 1 builds the document, renders it to PDF with LibreOffice and finds the
page of every heading; pass 2 rebuilds with those page numbers.
"""
import json
import os
import shutil
import subprocess
import sys

import fitz  # PyMuPDF

SOFFICE = shutil.which("soffice") or "/Applications/LibreOffice.app/Contents/MacOS/soffice"
DOCX, PDF = "crypto_research_report.docx", "crypto_research_report.pdf"
TOC = "data/research/_toc.json"


def build():
    subprocess.run([sys.executable, "src/build_report.py"], check=True)


def render():
    subprocess.run([SOFFICE, "--headless", "--convert-to", "pdf", "--outdir", ".", DOCX],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def heading_pages(heads):
    d = fitz.open(PDF)
    pages = []
    start = 2                              # skip title + contents pages
    for lvl, text in heads:
        key = text[:60]
        found = None
        for i in range(start, len(d)):
            lines = [ln.strip() for ln in d[i].get_text().splitlines()]
            if any(ln.startswith(key[:40]) for ln in lines):
                found = i; break
        if found is None:
            found = start
        start = found
        pages.append((lvl, text, found + 1))
    return pages


if __name__ == "__main__":
    if os.path.exists(TOC):
        os.remove(TOC)
    # pass 1: reserve one blank contents page
    json.dump([[1, "placeholder", 0]], open(TOC, "w"))
    build(); render()
    heads = json.load(open("data/research/_heads.json"))
    json.dump(heading_pages(heads), open(TOC, "w"))
    # pass 2: real contents
    build(); render()
    # verify the page numbers did not move
    check = heading_pages(heads)
    if check != json.load(open(TOC)):
        json.dump(check, open(TOC, "w")); build(); render()
    print(f"saved {DOCX} and {PDF}")
