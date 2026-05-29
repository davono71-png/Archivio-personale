# Architettura personal-archive-ai

## Flusso iniziale

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

## Componenti

- **GitHub**: codice, configurazione versionabile e documentazione.
- **VPS**: ambiente di test iniziale.
- **Docker Compose**: rende portabile lo stack verso mini PC con `git pull` e
  `docker compose up`.
- **n8n**: automazioni Gmail/Drive, download allegati, salvataggio su Drive e applicazione
  etichette.
- **CLI Python**: modulo operativo per regole YAML, OAuth Google, dry-run e tracciamento SQLite.
- **Database**: stato di email, file salvati, categoria assegnata, rinomina e stato elaborazione.
- **Config YAML**: categorie e mapping cartelle modificabili senza cambiare codice.

## Percorso evolutivo

1. usare la CLI per validare OAuth, Gmail API, Drive API e regole;
2. collegare n8n agli stessi file `config/`;
3. aggiungere download allegati e salvataggio in "Da Classificare";
4. integrare OCR e classificazione AI;
5. consolidare il database applicativo;
6. migrare lo stack da VPS a mini PC copiando repository e volumi necessari.
