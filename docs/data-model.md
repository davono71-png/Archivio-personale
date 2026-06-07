# Data model V1

Il modello dati V1 distingue in modo netto:

- **proprietario** del documento;
- **visibilita** del documento;
- **condivisioni** esplicite.

## Utenti

Gli utenti iniziali sono:

- Davide
- Ralitza

Non esiste un proprietario "Famiglia". Un documento e sempre di Davide o di Ralitza.

## Visibilita

La visibilita indica chi puo vedere il documento:

- `privato`: visibile solo al proprietario;
- `condiviso`: visibile anche agli utenti presenti in `document_shares`.

Esempio:

```text
owner_user_id = Davide
visibility = condiviso
document_shares = Ralitza/lettura
```

significa: il documento e di Davide, ma Ralitza puo leggerlo.

## Regola UX

La UI deve mostrare:

- filtro proprietario: Tutti, Davide, Ralitza;
- filtro visibilita: Tutti, Privati, Condivisi;
- azione rapida: "Rendi privato" o "Condividi".

## Schema SQL

Lo schema PostgreSQL/Supabase V1 e in:

```text
docs/database-postgres-v1.sql
```

## Knowledge base documenti ricorrenti

La tabella `document_patterns` serve a riconoscere documenti ripetitivi:

- Banco BPM;
- Enel;
- Allianz;
- Agenzia Entrate;
- Farmacia;
- Amazon.

Il sistema potra usare:

- mittente/provider;
- parole chiave;
- categoria corretta;
- proprietario predefinito;
- visibilita predefinita;
- esempi confermati.

Questo riduce chiamate a modelli costosi e accelera le classificazioni automatiche.
