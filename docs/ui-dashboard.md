# UI Dashboard

La dashboard e il futuro punto di controllo per l'utente.

## Obiettivi

- vedere lo stato della pipeline documentale;
- controllare documenti da classificare;
- approvare o rifiutare classificazioni AI;
- vedere scadenze;
- distinguere proprietari: Davide, Moglie, Famiglia, Azienda/Lavoro;
- avviare azioni controllate come OCR, import AnythingLLM e spostamento Drive.

## Stato attuale

La prima versione e statica e si trova in:

```text
frontend/
```

Serve per validare UX e layout prima di sviluppare backend/API.

## Avvio

```bash
docker compose --profile ui up -d dashboard
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

1. Sostituire i dati mock con API FastAPI.
2. Leggere `ai_review_items` da SQLite/PostgreSQL.
3. Aggiungere conferma/rifiuto reale delle review.
4. Mostrare dry-run spostamenti Drive.
5. Eseguire spostamenti solo dopo conferma esplicita.
6. Integrare ricerca AnythingLLM o rimando al workspace.
