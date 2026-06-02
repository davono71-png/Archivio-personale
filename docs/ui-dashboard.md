# UI Dashboard

La dashboard e il futuro punto di controllo per l'utente.

## Obiettivi

- vedere lo stato della pipeline documentale;
- controllare documenti da classificare;
- approvare o rifiutare classificazioni AI;
- cambiare categoria, proprietario e visibilita prima dello spostamento;
- aprire/modificare il file originale tramite link Google Drive quando disponibile;
- vedere scadenze;
- distinguere proprietari: Davide, Ralitza, Non chiaro;
- distinguere visibilita: privato, condiviso;
- avviare azioni controllate come OCR, import AnythingLLM e spostamento Drive.

## Stato attuale

La prima versione si trova in:

```text
frontend/
```

La UI legge dati reali da SQLite tramite una API leggera, ma mantiene fallback con dati demo se
l'API non risponde.

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

La dashboard e responsive. Su smartphone resta utile provare anche la modalita desktop per le
tabelle piu larghe, ma layout e filtri sono gia adattati a schermi piccoli.

## Evoluzione prevista

1. Estendere l'API leggera con dry-run spostamenti Drive.
2. Migrare da SQLite a PostgreSQL/Supabase quando il modello dati sara stabile.
3. Mostrare log degli errori di spostamento.
4. Eseguire spostamenti solo dopo conferma esplicita.
5. Implementare "Cestino documenti" come spostamento controllato verso una cartella dedicata.
6. Integrare ricerca AnythingLLM o rimando al workspace.

La versione attuale usa una API leggera in Python standard library:

```text
http://HOST:8090/api
```

La API legge:

- `DASHBOARD_DB`, default `database/personal-archive.sqlite3`;
- `DASHBOARD_INVENTORY`, default `database/inventory-da-classificare.csv`.
- `DASHBOARD_DRIVE_CONFIG`, default `config/drive-folders.yml`;
- `DASHBOARD_CREDENTIALS`, default `config/credentials.json`;
- `DASHBOARD_TOKEN`, default `database/token.json`.

Se l'inventario e disponibile, la UI associa le review ai link Drive e il nome documento diventa
cliccabile. Il link apre Google Drive in una nuova scheda, dove l'utente puo visionare o
modificare il file secondo i propri permessi Google.

Azioni operative disponibili:

- modifica categoria/proprietario/visibilita dalla riga o dal dettaglio;
- `Approva e sposta`: approva la review e tenta lo spostamento Drive nella cartella categoria;
- `Rifiuta`: marca la review come rejected;
- `Cestino documenti`: placeholder non distruttivo, marca la review come rejected finche non
  configuriamo la cartella cestino;
- `Cerca con AI`: usa AnythingLLM se sono configurati `ANYTHINGLLM_API_KEY` e
  `ANYTHINGLLM_WORKSPACE`.

Se l'API non risponde, la UI usa dati dimostrativi.
