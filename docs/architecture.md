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
- **AnythingLLM + Ollama**: ricerca AI e classificazione locale senza costi API esterne quando
  la qualita del modello locale e sufficiente.
- **Database**: stato di email, file salvati, categoria assegnata, rinomina e stato elaborazione.
- **Data model**: proprietari iniziali Davide/Ralitza, visibilita `privato`/`condiviso` e
  condivisioni esplicite sono descritti in `docs/data-model.md`.
- **Config YAML**: categorie e mapping cartelle modificabili senza cambiare codice.
- **Policy classificazione**: soglie di confidenza e knowledge base dei documenti ricorrenti
  sono descritte in `docs/classification-policy.md`.

## Percorso evolutivo

La roadmap operativa aggiornata e in:

```text
docs/roadmap.md
```
