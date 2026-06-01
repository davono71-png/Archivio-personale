# Dashboard UI

Prima dashboard statica per l'archivio personale.

Obiettivo:

- visualizzare stato pipeline;
- mostrare documenti proposti dall'AI;
- simulare approvazione/rifiuto;
- ragionare sulla futura UX mobile/desktop;
- preparare la futura integrazione con backend FastAPI/SQLite.

Questa versione e volutamente statica: i dati sono mock in `app.js`.
Quando il backend sara pronto, la dashboard usera API reali per leggere review, stati e azioni.

## Avvio via Docker

```bash
docker compose --profile ui up -d dashboard
```

Apri:

```text
http://localhost:8080
```

Su VPS:

```text
http://IP_DELLA_VPS:8080
```

Per fermare:

```bash
docker compose --profile ui stop dashboard
```
