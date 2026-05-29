# Database

In sviluppo locale la CLI usa SQLite, con percorso consigliato:

```text
database/personal-archive.sqlite3
```

Il file SQLite non va committato. Lo schema viene creato automaticamente da:

```bash
gmail-drive-archiver init-db --db database/personal-archive.sqlite3
```

Nel Docker Compose n8n usa PostgreSQL per il proprio stato interno. La migrazione del tracciamento
applicativo da SQLite a PostgreSQL puo essere aggiunta quando i workflow n8n saranno stabilizzati.
