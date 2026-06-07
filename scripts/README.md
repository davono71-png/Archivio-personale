# Scripts

Questa cartella contiene script operativi richiamabili manualmente o da n8n.

La CLI Python principale resta installabile dal package `gmail-drive-archiver`:

```bash
gmail-drive-archiver sync --dry-run
```

Per l'uso dentro container o VPS, usa `run-archiver.sh` dopo avere montato `config/`,
`database/` e il file OAuth `credentials.json`.
