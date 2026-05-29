# Archivio personale Gmail + Drive

CLI Python per archiviare automaticamente email Gmail e documenti Google Drive personali.
Il progetto usa Google OAuth, Gmail API, Drive API, regole YAML, modalita dry-run e SQLite
per tracciare gli elementi gia processati.

## Funzionalita

- OAuth Google locale con salvataggio del token.
- Archiviazione Gmail tramite rimozione dell'etichetta `INBOX`.
- Applicazione opzionale di una label Gmail e marcatura come letto.
- Spostamento file Drive in una cartella archivio.
- Regole dichiarative in YAML.
- Modalita `--dry-run` per vedere le azioni senza modificare Gmail/Drive e senza scrivere
  nuovi elementi nel database.
- Database SQLite per evitare di processare piu volte lo stesso elemento con la stessa regola.

## Requisiti

- Python 3.10 o superiore.
- Un account Google personale.
- Un progetto Google Cloud con Gmail API e Drive API abilitate.

## Installazione

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Verifica che la CLI sia disponibile:

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
7. Salva il JSON in locale, ad esempio:

```bash
mkdir -p ~/.config/gmail-drive-archiver
mv ~/Downloads/client_secret_*.json ~/.config/gmail-drive-archiver/credentials.json
```

Alla prima esecuzione `sync`, la CLI aprira il browser per il consenso OAuth e salvera il
token in `~/.config/gmail-drive-archiver/token.json`.

### Scope OAuth usati

La CLI richiede:

- `https://www.googleapis.com/auth/gmail.modify`
- `https://www.googleapis.com/auth/drive`

Questi scope permettono rispettivamente di modificare label/stato dei messaggi Gmail e di
spostare file Drive.

## Regole YAML

Vedi `examples/rules.yaml` per un esempio completo.

```yaml
gmail:
  - name: newsletter-vecchie
    query: "category:promotions older_than:30d"
    label: "Archivio/Newsletter"
    mark_read: true
    max_items: 100

drive:
  - name: pdf-vecchi
    query: "mimeType='application/pdf' and modifiedTime < '2024-01-01T00:00:00' and trashed = false"
    target_folder_id: "ID_CARTELLA_ARCHIVIO_DRIVE"
    remove_from_current_parents: true
    max_items: 50
```

### Campi Gmail

- `name`: nome univoco della regola, usato anche nel database SQLite.
- `query`: query Gmail, con la stessa sintassi della ricerca Gmail.
- `label`: label da applicare prima dell'archiviazione; viene creata se non esiste.
- `mark_read`: se `true`, rimuove anche l'etichetta `UNREAD`.
- `max_items`: limite opzionale di messaggi da processare per esecuzione.

L'archiviazione Gmail rimuove `INBOX`, quindi il messaggio resta disponibile in "Tutti i
messaggi" e nelle eventuali label applicate.

### Campi Drive

- `name`: nome univoco della regola.
- `query`: query Drive API `files.list`.
- `target_folder_id`: ID della cartella Drive dove spostare i documenti.
- `remove_from_current_parents`: se `true`, rimuove i parent precedenti e sposta davvero il
  file; se `false`, aggiunge solo la cartella archivio.
- `max_items`: limite opzionale di file da processare per esecuzione.

Per trovare l'ID di una cartella Drive, aprila nel browser e copia la parte finale dell'URL:

```text
https://drive.google.com/drive/folders/QUESTO_E_L_ID
```

## Utilizzo

Inizializza il database SQLite:

```bash
gmail-drive-archiver init-db
```

Esegui una simulazione:

```bash
gmail-drive-archiver sync \
  --rules examples/rules.yaml \
  --credentials ~/.config/gmail-drive-archiver/credentials.json \
  --dry-run
```

Esegui l'archiviazione reale:

```bash
gmail-drive-archiver sync \
  --rules examples/rules.yaml \
  --credentials ~/.config/gmail-drive-archiver/credentials.json
```

Limita l'esecuzione a un solo servizio:

```bash
gmail-drive-archiver sync \
  --rules examples/rules.yaml \
  --credentials ~/.config/gmail-drive-archiver/credentials.json \
  --service gmail
```

Percorsi predefiniti:

- Token OAuth: `~/.config/gmail-drive-archiver/token.json`
- Database SQLite: `~/.config/gmail-drive-archiver/processed.sqlite3`

Puoi sovrascriverli con `--token` e `--db`.

## Sicurezza e note operative

- Non committare `credentials.json`, `token.json` o database SQLite contenenti dati personali.
- Prova sempre nuove regole con `--dry-run`.
- Se cambi il significato di una regola esistente ma riusi lo stesso `name`, gli elementi gia
  registrati nel database resteranno saltati. Usa un nuovo `name` per riprocessarli oppure
  pulisci consapevolmente il database.
- L'app e pensata per uso personale; prima di renderla disponibile ad altri utenti, rivedi
  consenso OAuth, verifica app Google e gestione dei dati.

## Sviluppo

Esegui i test:

```bash
PYTHONPATH=src python -m unittest discover
```

Controlla la sintassi Python:

```bash
python -m compileall src tests
```
