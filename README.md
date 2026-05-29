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
