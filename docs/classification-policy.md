# Policy di classificazione

Questa policy guida il passaggio da classificazione euristica/AI a decisione operativa.
Non e tassativa: serve come regola di buon senso per ridurre costi, interventi manuali e
chiamate a modelli costosi.

## Routing per confidenza

Ogni classificazione deve produrre almeno:

```json
{
  "categoria": "Banca",
  "confidenza": 99
}
```

Regola operativa:

| Confidenza | Azione |
| --- | --- |
| `> 95` | Archivia direttamente, salvo categorie sensibili o regole specifiche. |
| `70-95` | Usa un modello economico/veloce, ad esempio GPT mini, per seconda opinione. |
| `< 70` | Chiedi conferma a Davide. |

## Interpretazione

- `> 95`: documento molto riconoscibile, ad esempio bolletta Enel, estratto Banco BPM,
  ricevuta Amazon, polizza Allianz.
- `70-95`: documento probabilmente classificabile, ma con ambiguita su categoria,
  proprietario, scadenza o duplicati.
- `< 70`: documento poco leggibile, incompleto, OCR incerto, file tecnico, o contenuto fuori
  dai pattern noti.

## Knowledge base dei documenti ricorrenti

Molti documenti si ripetono per mittente, layout e parole chiave:

- Banco BPM
- Enel
- Allianz
- Agenzia Entrate
- Farmacia
- Amazon

Dopo alcuni lotti, il sistema dovra costruire una knowledge base con:

- mittente/origine;
- parole chiave;
- layout o struttura ricorrente;
- categoria corretta;
- proprietario frequente;
- azione consigliata;
- esempi confermati.

Esempio:

```json
{
  "provider": "Enel",
  "keywords": ["bolletta", "energia", "scadenza", "totale da pagare"],
  "category": "Casa",
  "subcategory": "Utenze",
  "owner": "Davide",
  "visibility": "condiviso",
  "default_action": "Archivia"
}
```

## Obiettivo costi

Il flusso deve usare i modelli costosi solo quando servono:

1. classificazione locale/euristica;
2. knowledge base ricorrente;
3. modello economico per casi medi;
4. modello potente solo per casi complessi o review manuali.

Questa stratificazione dovrebbe ridurre drasticamente i costi rispetto a inviare ogni documento
intero a un modello premium.
