# UI Dashboard

La dashboard e il futuro punto di controllo per l'utente.

## Obiettivi

- vedere lo stato della pipeline documentale;
- controllare documenti da classificare;
- approvare o rifiutare classificazioni AI;
- vedere scadenze;
- distinguere proprietari: Davide, Ralitza, Non chiaro;
- distinguere visibilita: privato, condiviso;
- avviare azioni controllate come OCR, import AnythingLLM e spostamento Drive.

## Stato attuale

La prima versione e statica e si trova in:

```text
frontend/
```

Serve per validare UX e layout prima di sviluppare backend/API.

## Avvio

```bash
docker compose --profile ui up -d dashboard dashboard-api
```

Locale:

```text
http://localhost:8080
```

VPS:

```text
http://IP_DELLA_VPS:8080
```

## Note mobile

Su smartphone puo essere utile aprire il sito in modalita desktop. La dashboard mantiene una
larghezza minima per preservare la tabella documenti.

## Evoluzione prevista

1. Estendere l'API leggera con dry-run spostamenti Drive.
2. Migrare da SQLite a PostgreSQL/Supabase quando il modello dati sara stabile.
3. Mostrare log degli errori di spostamento.
4. Eseguire spostamenti solo dopo conferma esplicita.
5. Integrare ricerca AnythingLLM o rimando al workspace.

La versione attuale usa una API leggera in Python standard library:

```text
http://HOST:8090/api
```

La API legge:

- `DASHBOARD_DB`, default `database/personal-archive.sqlite3`;
- `DASHBOARD_INVENTORY`, default `database/inventory-da-classificare.csv`.

Se l'inventario e disponibile, la UI associa le review ai link Drive e il nome documento diventa
cliccabile. Il link apre Google Drive in una nuova scheda, dove l'utente puo visionare o
modificare il file secondo i propri permessi Google.

Se l'API non risponde, la UI usa dati dimostrativi.
