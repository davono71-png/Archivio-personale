# Prompt AnythingLLM - classificazione documenti

Usa questo prompt nel workspace AnythingLLM dopo avere importato i file generati da:

```bash
gmail-drive-archiver prepare-anythingllm \
  --inventory database/inventory-da-classificare.csv \
  --text-dir database/extracted-text \
  --categories config/categories.yml \
  --output-dir database/anythingllm-import
```

## Prompt

```text
Analizza i documenti caricati nel workspace.

Per ogni documento che riesci a identificare, restituisci una tabella Markdown con queste colonne:

1. Nome documento
2. Categoria principale
3. Sottocategoria proposta
4. Proprietario probabile
5. Visibilita suggerita
6. Data rilevante
7. Scadenza
8. Azione consigliata
9. Duplicato di
10. Confidenza
11. Motivo sintetico

Categorie principali ammesse:
- Banca
- Salute
- Assicurazioni
- Casa
- Auto
- Fisco
- Garanzie
- Sport
- Tecnologia
- Viaggi
- Lavoro
- Alimentazione
- Varie

Proprietario probabile ammesso:
- Davide
- Ralitza
- Non chiaro

Visibilita suggerita ammessa:
- privato
- condiviso

Azione consigliata ammessa:
- Archivia
- Da verificare
- Ignora
- OCR richiesto
- Duplicato

Regole:
- Non inventare dati non presenti nei documenti.
- Se una data non e presente, scrivi "Non presente".
- Se una scadenza non e presente, scrivi "Non presente".
- Se non sei sicuro del proprietario, scrivi "Non chiaro".
- Non usare "Famiglia" come proprietario: se il documento riguarda entrambi, scegli il proprietario piu probabile e imposta visibilita "condiviso".
- Se trovi nomi diversi da Davide o Ralitza, tratta il proprietario come Davide salvo evidenza esplicita contraria.
- Bollette energia/gas/acqua/utenze vanno in categoria "Casa", non "Banca".
- Estratti conto, bonifici, saldi, giacenze e conti correnti vanno in categoria "Banca".
- Documenti fiscali, Agenzia Entrate, IVA, dichiarazioni e fatture vanno in categoria "Fisco".
- Non creare nuove categorie fuori dall'elenco ammesso: se non rientra chiaramente, usa "Varie".
- Se il documento e personale, sanitario, fiscale o sensibile e riguarda una sola persona, suggerisci visibilita "privato".
- Se un file sembra tecnico, vuoto o residuale, usa categoria "Varie" e azione "Ignora" salvo chiara utilita.
- Se due documenti sembrano duplicati o copie, segnala "Duplicato" in Azione consigliata e compila "Duplicato di".
- Se un documento contiene solo metadati incompleti o testo insufficiente, usa "Da verificare".
- La confidenza deve essere un numero da 0 a 100.
- Usa confidenza >95 solo quando categoria e azione sono molto evidenti.
- Usa confidenza tra 70 e 95 quando il documento e probabile ma richiede seconda opinione.
- Usa confidenza <70 quando serve conferma manuale di Davide.
- Nel motivo sintetico spiega brevemente quali elementi del documento giustificano la categoria.
- Mantieni la risposta compatta ma completa.
```

## Prompt breve per ricerca

```text
Cerca nei documenti caricati e rispondi indicando:
- documenti rilevanti;
- categoria probabile;
- motivazione;
- eventuali date o scadenze;
- link o nome documento se disponibile.

Domanda: [SCRIVI QUI LA DOMANDA]
```

## Esempi di domande

```text
Quali documenti parlano di garanzie?
```

```text
Quali documenti sembrano collegati al lavoro?
```

```text
Trova documenti relativi a bollette o pagamenti.
```

```text
Quali documenti hanno una scadenza?
```
