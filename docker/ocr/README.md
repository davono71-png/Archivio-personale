# OCR worker

Container per la fase OCR/testo.

Include:

- Tesseract OCR con lingua italiana e inglese;
- OCRmyPDF;
- Poppler (`pdftotext`);
- la CLI `gmail-drive-archiver`.

Uso previsto:

```bash
docker compose run --rm ocr-worker gmail-drive-archiver ocr-plan \
  --input database/inventory-da-classificare.csv
```

Quando i file saranno scaricati in `database/downloads`, il container potra estrarre testo con:

```bash
docker compose run --rm ocr-worker gmail-drive-archiver extract-text \
  --input database/inventory-da-classificare.csv \
  --files-dir database/downloads \
  --output-dir database/extracted-text \
  --report database/extract-text-report.csv
```

Il download automatico da Drive e l'OCR massivo verranno aggiunti come step successivi.
