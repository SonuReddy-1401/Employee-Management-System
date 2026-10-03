# Pandoc Report Export Instructions

## Export Command (Docker `pandoc/core:latest`)

To export `docs/report/FINAL_REPORT.md` to `docs/report/FINAL_REPORT.docx` with automated Table of Contents, Section Numbering, and embedded figures, execute the following command:

```bash
docker run --rm -v "$(pwd):/data" pandoc/core:latest /data/docs/report/FINAL_REPORT.md -o /data/docs/report/FINAL_REPORT.docx --toc --number-sections --resource-path=/data/docs/img/diagrams:/data/docs/img/screenshots:/data/docs/img
```

## PowerShell Equivalent Command (Windows)

```powershell
docker run --rm -v "${PWD}:/data" pandoc/core:latest /data/docs/report/FINAL_REPORT.md -o /data/docs/report/FINAL_REPORT.docx --toc --number-sections --resource-path=/data/docs/img/diagrams:/data/docs/img/screenshots:/data/docs/img
```
