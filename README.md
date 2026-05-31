# personal-archive-ai

Repository per un archivio personale automatizzato basato su GitHub, Docker Compose, n8n,
Google Gmail/Drive e una CLI Python di supporto.

L'obiettivo e partire su VPS e poter spostare lo stesso stack su mini PC con:

```bash
git pull
docker compose up -d
```

## Struttura

```text
personal-archive-ai
├── docker-compose.yml
├── n8n/
├── scripts/
├── config/
│   ├── categories.yml
│   ├── gmail-rules.yml
│   └── drive-folders.yml
├── database/
├── docs/
├── src/
├── tests/
└── README.md
```

## Architettura iniziale

```text
Gmail
  |
  v
n8n
  |
  v
Classificazione regole
  |
  v
Google Drive / Da Classificare
  |
  v
OCR + AI
  |
  v
Cartella finale
```

Dettagli: `docs/architecture.md`.

## Componenti inclusi

- **Docker Compose** con n8n e PostgreSQL per lo stato interno di n8n.
- **n8n/** come cartella per gli export dei workflow.
- **AnythingLLM** opzionale via profilo Docker `ai`.
- **config/** con categorie, regole Gmail e mapping cartelle Drive.
- **database/** per SQLite locale della CLI e note operative.
- **scripts/** con wrapper eseguibile per l'archiver.
- **CLI Python** installabile (`gmail-drive-archiver`) con:
  - OAuth Google locale;
  - Gmail API;
  - Drive API;
  - modalita `--dry-run`;
  - regole YAML;
  - SQLite per elementi gia processati, email, file e classificazioni future.

## Requisiti

- Python 3.10 o superiore.
- Docker e Docker Compose.
- Un account Google personale.
- Un progetto Google Cloud con Gmail API e Drive API abilitate.

## Avvio stack n8n

Crea un file `.env` locale, non committato:

```bash
POSTGRES_DB=personal_archive
POSTGRES_USER=archive
POSTGRES_PASSWORD=cambia_questa_password
N8N_ENCRYPTION_KEY=usa_una_stringa_lunga_random
N8N_HOST=localhost
N8N_PROTOCOL=http
N8N_PORT=5678
ANYTHINGLLM_PORT=3001
OLLAMA_PORT=11434
OLLAMA_BASE_PATH=http://ollama:11434
OLLAMA_MODEL_PREF=llama3.2:3b
TZ=Europe/Rome
```

Avvia:

```bash
docker compose up -d
```

Apri n8n su:

```text
http://localhost:5678
```

## Avvio AnythingLLM

AnythingLLM e configurato come servizio opzionale nel profilo Docker `ai`.

```bash
docker compose --profile ai up -d anythingllm
```

Apri:

```text
http://localhost:3001
```

Lo storage locale resta in `anythingllm/storage/`, ignorato da Git.

### Uso con Ollama locale

Per evitare costi API Gemini/OpenAI puoi usare Ollama nel profilo Docker `ai`.

Avvia Ollama e AnythingLLM:

```bash
docker compose --profile ai up -d ollama anythingllm
```

Scarica un modello leggero:

```bash
docker compose --profile ai exec ollama ollama pull llama3.2:3b
```

Alternative piu capaci ma piu pesanti:

```bash
docker compose --profile ai exec ollama ollama pull qwen2.5:7b
docker compose --profile ai exec ollama ollama pull llama3.1:8b
```

In AnythingLLM imposta:

```text
LLM Provider: Ollama
Base URL: http://ollama:11434
Model: llama3.2:3b
```

Se usi AnythingLLM dal browser ma Ollama gira nel container Docker, usa comunque
`http://ollama:11434` nelle impostazioni interne di AnythingLLM, perche i container si parlano
tramite la rete Docker.

## Installazione CLI Python

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -e .
```

Verifica:

```bash
gmail-drive-archiver --help
```

## Configurazione Google Cloud

1. Apri [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un nuovo progetto o selezionane uno esistente.
3. Vai in **APIs & Services > Library** e abilita:
   - **Gmail API**
   - **Google Drive API**
4. Vai in **APIs & Services > OAuth consent screen**.
   - Seleziona **External** per un account personale.
   - Compila nome app, email supporto e contatto sviluppatore.
   - Aggiungi il tuo account tra i **Test users** se l'app resta in modalita test.
5. Vai in **APIs & Services > Credentials**.
6. Crea credenziali **OAuth client ID**.
   - Application type: **Desktop app**.
   - Scarica il file JSON.
7. Salva il JSON fuori da Git oppure in `config/credentials.json` locale, ignorato da Git:

```bash
cp ~/Downloads/client_secret_*.json config/credentials.json
```

Alla prima esecuzione `sync`, la CLI apre il browser per il consenso OAuth e salva il token
nel percorso indicato da `--token`.

Scope OAuth usati:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/drive`

## Configurazione YAML

### `config/categories.yml`

Elenco modificabile delle categorie:

```yaml
categories:
  - Banca
  - Salute
  - Assicurazioni
  - Casa
  - Auto
  - Fisco
  - Garanzie
  - Sport
  - Tecnologia
  - Viaggi
  - Lavoro
  - Alimentazione
  - Varie
```

### `config/gmail-rules.yml`

Regole Gmail con sintassi di ricerca Gmail:

```yaml
gmail:
  - name: allegati-da-archiviare
    query: "has:attachment newer_than:365d -label:Archivio/Processato"
    label: "Archivio/Processato"
    mark_read: false
    max_items: 100
```

### `config/drive-folders.yml`

Mapping cartelle Drive e regole Drive API:

```yaml
drive:
  inbox_folder_id: "INSERISCI_ID_CARTELLA_DA_CLASSIFICARE"
  archive_root_folder_id: "INSERISCI_ID_CARTELLA_ARCHIVIO"
  category_folders:
    Banca: "INSERISCI_ID_CARTELLA_BANCA"
    Lavoro: "INSERISCI_ID_CARTELLA_LAVORO"
    Alimentazione: "INSERISCI_ID_CARTELLA_ALIMENTAZIONE"
    Varie: "INSERISCI_ID_CARTELLA_VARIE"
  rules:
    - name: pdf-vecchi
      query: "mimeType='application/pdf' and trashed = false"
      target_folder_id: "INSERISCI_ID_CARTELLA_ARCHIVIO"
```

Per trovare l'ID di una cartella Drive, aprila nel browser e copia la parte finale dell'URL:

```text
https://drive.google.com/drive/folders/QUESTO_E_L_ID
```

## Uso CLI

Inizializza SQLite:

```bash
gmail-drive-archiver init-db --db database/personal-archive.sqlite3
```

Dry-run con configurazione separata:

```bash
gmail-drive-archiver sync \
  --gmail-rules config/gmail-rules.yml \
  --drive-config config/drive-folders.yml \
  --categories config/categories.yml \
  --credentials config/credentials.json \
  --token database/token.json \
  --db database/personal-archive.sqlite3 \
  --dry-run
```

Esecuzione reale:

```bash
gmail-drive-archiver sync \
  --credentials config/credentials.json \
  --token database/token.json \
  --db database/personal-archive.sqlite3
```

Wrapper:

```bash
sh scripts/run-archiver.sh --dry-run
```

La CLI supporta ancora `--rules examples/rules.yaml` per un singolo YAML combinato.

### Inventario sicuro di "Da Classificare"

Per vedere cosa c'e nella cartella `drive.inbox_folder_id` senza spostare nulla:

```bash
gmail-drive-archiver inventory \
  --credentials config/credentials.json \
  --token database/token.json \
  --drive-config config/drive-folders.yml \
  --max-items 100
```

Per esportare un CSV da usare nella fase OCR/AI/classificazione:

```bash
gmail-drive-archiver inventory \
  --credentials config/credentials.json \
  --token database/token.json \
  --drive-config config/drive-folders.yml \
  --max-items 500 \
  --format csv \
  --output database/inventory-da-classificare.csv
```

Il comando `inventory` e read-only: legge i metadati dei file Drive ma non modifica cartelle,
nomi, label o database.

Per scaricare localmente un piccolo lotto di file dell'inventario:

```bash
gmail-drive-archiver download-inventory \
  --input database/inventory-da-classificare.csv \
  --credentials config/credentials.json \
  --token database/token.json \
  --output-dir database/downloads \
  --report database/download-report.csv \
  --limit 20
```

Il comando `download-inventory` non modifica Drive: scarica copie locali in
`database/downloads`. I file Google Docs/Sheets/Slides vengono esportati rispettivamente come
DOCX/XLSX/PPTX quando possibile. Senza `--overwrite`, i file gia presenti vengono saltati.

Per analizzare il CSV e ottenere un primo riassunto per tipi file, estensioni e categorie
probabili dai nomi:

```bash
gmail-drive-archiver analyze-inventory \
  --input database/inventory-da-classificare.csv \
  --categories config/categories.yml
```

Per salvare il risultato in JSON:

```bash
gmail-drive-archiver analyze-inventory \
  --input database/inventory-da-classificare.csv \
  --categories config/categories.yml \
  --format json \
  --output database/inventory-analysis.json
```

`analyze-inventory` non usa ancora OCR o AI: e una prima analisi locale basata su metadati,
estensioni e parole chiave nei nomi file. Serve a capire il contenuto della cartella prima di
decidere regole, OCR e AnythingLLM.

Per preparare la fase OCR senza installare ancora strumenti pesanti:

```bash
gmail-drive-archiver ocr-plan \
  --input database/inventory-da-classificare.csv
```

Il comando divide l'inventario in:

- **Candidati OCR**: PDF e immagini;
- **Documenti testuali**: DOC/DOCX/ODT/TXT da cui estrarre testo;
- **File strutturati**: CSV/XLS/XLSX;
- **File tecnici / calendario / web**: XML/HTML/ICS;
- **Da valutare manualmente**: estensioni o MIME type non riconosciuti.

Per salvare il piano in JSON:

```bash
gmail-drive-archiver ocr-plan \
  --input database/inventory-da-classificare.csv \
  --format json \
  --output database/ocr-plan.json
```

`ocr-plan` e read-only: non scarica file, non esegue OCR e non modifica Drive.

### Estrazione testo locale

Quando i file dell'inventario saranno disponibili localmente in `database/downloads`, puoi
estrarre testo dove possibile:

```bash
gmail-drive-archiver extract-text \
  --input database/inventory-da-classificare.csv \
  --files-dir database/downloads \
  --output-dir database/extracted-text \
  --report database/extract-text-report.csv
```

Il comando:

- legge file di testo, CSV, XML/HTML/ICS;
- estrae testo base da DOCX e XLSX usando libreria standard Python;
- usa `pdftotext` se disponibile per PDF gia testuali;
- marca PDF/immagini come `requires_ocr` quando serve OCR vero;
- scrive un report CSV con esito per ogni file.

Per analizzare il contenuto dei testi gia estratti:

```bash
gmail-drive-archiver analyze-text \
  --text-dir database/extracted-text \
  --categories config/categories.yml
```

Per salvare un JSON:

```bash
gmail-drive-archiver analyze-text \
  --text-dir database/extracted-text \
  --categories config/categories.yml \
  --format json \
  --output database/text-analysis.json
```

`analyze-text` usa le stesse categorie e parole chiave di `analyze-inventory`, ma lavora sul
contenuto estratto invece che solo sul nome file.

### Preparazione import AnythingLLM

Per creare una cartella importabile in AnythingLLM:

```bash
gmail-drive-archiver prepare-anythingllm \
  --inventory database/inventory-da-classificare.csv \
  --text-dir database/extracted-text \
  --categories config/categories.yml \
  --output-dir database/anythingllm-import
```

Il comando crea:

- file `.txt` con intestazione metadati e contenuto estratto;
- `manifest.jsonl` con nome originale, ID Drive, link Drive, categoria provvisoria e percorso
  del file esportato.

La cartella `database/anythingllm-import` puo poi essere importata in un workspace AnythingLLM.
Le categorie generate restano provvisorie: AnythingLLM/AI servira per ricerca e classificazione
piu intelligente.

Prompt consigliato per classificare i documenti importati:

```text
docs/prompts/anythingllm-classification.md
```

Per usare gli strumenti OCR dentro Docker:

```bash
docker compose --profile tools build ocr-worker
docker compose run --rm ocr-worker gmail-drive-archiver ocr-plan \
  --input database/inventory-da-classificare.csv
```

Il container OCR include Tesseract, lingua italiana/inglese, OCRmyPDF e Poppler. Il download
automatico dei file Drive e l'OCR massivo sono step successivi.

## Database applicativo

SQLite crea automaticamente:

- `processed_items`: idempotenza per Gmail/Drive;
- `email_messages`: email processate;
- `drive_files`: file salvati/spostati, categoria e stato;
- `file_classifications`: cronologia delle classificazioni OCR/AI future.

## Sicurezza e note operative

- Non committare `.env`, `credentials.json`, `token.json` o database SQLite.
- Prova sempre nuove regole con `--dry-run`.
- Se cambi il significato di una regola ma riusi lo stesso `name`, gli elementi gia registrati
  resteranno saltati; usa un nuovo `name` per riprocessarli.
- Gli export n8n dovranno evitare credenziali hard-coded.

## Sviluppo

Esegui i test:

```bash
PYTHONPATH=src python3 -m unittest discover tests
```

Controlla la sintassi Python:

```bash
python3 -m compileall src tests
```
