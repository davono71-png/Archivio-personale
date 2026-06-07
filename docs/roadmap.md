# Roadmap operativa

## Stato attuale

Il progetto ha gia validato il ciclo principale sui documenti Drive:

1. inventario cartella `Da Classificare`;
2. download locale da Drive;
3. estrazione testo da PDF/DOCX/XLSX/CSV/HTML/XML/ICS;
4. piano OCR per immagini e file non leggibili;
5. preparazione batch per AnythingLLM/GPT mini;
6. import classificazioni AI da tabella Markdown;
7. normalizzazione categorie/proprietari/visibilita;
8. riepilogo review in SQLite;
9. dry-run e primo spostamento reale su Drive;
10. dashboard UI collegata a SQLite tramite API leggera.

## Regole dati correnti

- Proprietari ammessi: Davide, Ralitza, Non chiaro.
- Tutti gli altri nomi rilevati dall'AI vengono trattati come Davide, salvo futura estensione.
- Visibilita: `privato` o `condiviso`.
- Categorie chiuse: Banca, Salute, Assicurazioni, Casa, Auto, Fisco, Garanzie, Sport,
  Tecnologia, Viaggi, Lavoro, Alimentazione, Varie.
- Bollette energia/gas/acqua/utenze -> Casa.
- Estratti conto, bonifici, saldi, giacenze -> Banca.
- Agenzia Entrate, IVA, dichiarazioni, fatture -> Fisco.

## Prossimi step immediati

### 1. Pulizia review duplicate

Problema osservato: alcune review sono state importate due volte.

Da aggiungere:

```text
gmail-drive-archiver dedupe-ai-reviews
```

Obiettivo:

- eliminare duplicati su `document_name + category + recommended_action`;
- mantenere la riga piu recente o quella gia applicata;
- non perdere review applicate.

### 2. Test UI reale

La dashboard deve essere usata come punto di controllo:

- verificare review reali da SQLite;
- aprire file Drive dal titolo documento;
- approvare/rifiutare dalla UI;
- controllare responsive da cellulare;
- correggere UX prima di aggiungere funzioni distruttive.

### 3. Dry-run spostamenti da UI/API

La CLI ha gia:

```text
apply-review-moves
```

Da esporre nella UI/API:

- mostra piano spostamenti;
- mostra blocchi `not_found`, `ambiguous`, `missing_target_folder`;
- richiedere conferma esplicita prima di `--apply`.

### 4. Email

La base per email testuali esiste:

```text
export-gmail-text
```

Prossimi passi email:

- esportare email con label `Da archiviare`;
- importarle in AnythingLLM come documenti;
- aggiungere download allegati Gmail;
- tracciare email solo testo e allegati con lo stesso modello documentale.

### 5. Automazione

Quando i comandi sono stabili:

- orchestrazione con n8n;
- job periodici su VPS;
- dashboard per approvazione manuale;
- archiviazione automatica solo con confidenza alta e pattern noti.

## Step successivi non immediati

- Migrazione SQLite -> PostgreSQL/Supabase.
- RLS/security model per Davide/Ralitza.
- UI React vera con backend FastAPI.
- Modulo iCloud IMAP.
- Modulo scanner/mobile/WhatsApp.
- Knowledge base ricorrenti per Banco BPM, Enel, Allianz, Agenzia Entrate, Farmacia, Amazon.
