# n8n workflows

Questa cartella e destinata agli export JSON dei workflow n8n.

Flusso previsto:

1. leggere Gmail;
2. scaricare allegati;
3. salvare gli allegati nella cartella Drive "Da Classificare";
4. registrare email e file nel database;
5. avviare OCR + classificazione AI;
6. spostare il file nella cartella finale;
7. applicare etichette Gmail/Drive.

Gli export n8n non sono ancora inclusi per evitare credenziali o ID personali hard-coded.
