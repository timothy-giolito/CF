from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, unquote
import webbrowser
import os
import json

# --- 1. LOGICA DI CALCOLO (Invariata) ---
def calcola_codice_fiscale(nome, cognome, giorno, mese, anno, sesso, codice_catastale):
    def norm(s): return "".join(c.upper() for c in s if c.isalpha())
    def cons_voc(s): 
        s = norm(s)
        return [c for c in s if c not in 'AEIOU'], [c for c in s if c in 'AEIOU']

    # Cognome
    c, v = cons_voc(cognome)
    cod_c = (c + v + ['X']*3)[:3]
    # Nome
    c, v = cons_voc(nome)
    cod_n = [c[0], c[2], c[3]] if len(c) >= 4 else (c + v + ['X']*3)[:3]
    # Data
    aa = str(anno)[-2:].zfill(2)
    mm = "ABCDEHLMPRST"[int(mese)-1]
    gg = str(int(giorno) + (40 if sesso == 'F' else 0)).zfill(2)
    
    parziale = "".join(cod_c) + "".join(cod_n) + aa + mm + gg + codice_catastale
    
    # Check Digit
    dispari = {c:v for c,v in zip('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ', [1,0,5,7,9,13,15,17,19,21,1,0,5,7,9,13,15,17,19,21,2,4,18,20,11,3,6,8,12,14,16,10,22,25,24,23])}
    somma = 0
    for i, char in enumerate(parziale):
        if (i+1)%2 != 0: somma += dispari.get(char, 0)
        else: somma += (int(char) if char.isdigit() else ord(char)-ord('A'))
            
    return parziale + chr(65 + somma % 26)

# --- 2. CARICAMENTO DATI CSV ---
dizionario_luoghi = {}
html_options_luoghi = "" # Stringa HTML pre-generata per il menu a tendina

def carica_dati():
    global dizionario_luoghi, html_options_luoghi
    print("--- Caricamento database... ---")
    temp_list = []
    
    # Funzione helper per leggere
    def leggi(fname, is_comune):
        try:
            with open(fname, 'r', encoding='utf-8-sig', errors='replace') as f:
                for line in f:
                    p = line.strip().split(';')
                    if is_comune and len(p) > 18:
                        label = f"{p[6].strip()} ({p[13].strip()})"
                        cod = p[18].strip()
                        dizionario_luoghi[label] = cod
                        temp_list.append(label)
                    elif not is_comune and len(p) > 9:
                        label = f"{p[6].strip()} (Estero)"
                        cod = p[9].strip()
                        dizionario_luoghi[label] = cod
                        temp_list.append(label)
        except Exception as e: print(f"Errore file {fname}: {e}")

    leggi('comuni.csv', True)
    leggi('ee.csv', False)
    
    temp_list.sort()
    # Creiamo una stringa gigante di <option> per l'HTML
    html_options_luoghi = "\n".join([f'<option value="{x}">' for x in temp_list])
    print("Dati caricati.")

# --- 3. GESTIONE SERVER WEB (Nativo) ---
class RequestHandler(BaseHTTPRequestHandler):
    
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            with open('templates/index.html', 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Rimpiazza i segnaposto
            content = content.replace('{OPZIONI_LUOGHI}', html_options_luoghi)
            # Sostituisce il box del risultato con una stringa vuota al primo caricamento
            content = content.replace('{RISULTATO_BOX}', '') 
            
            self.wfile.write(content.encode('utf-8'))
            
        elif self.path.endswith('.css'):
            # Serve il file CSS
            try:
                with open(f".{self.path}", 'r', encoding='utf-8') as f:
                    css_content = f.read()
                self.send_response(200)
                self.send_header('Content-type', 'text/css')
                self.end_headers()
                self.wfile.write(css_content.encode('utf-8'))
            except:
                self.send_error(404)

    def do_POST(self):
        if self.path == '/calcola':
            # Legge i dati inviati dal form
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = parse_qs(post_data)
            
            # Estrae i valori
            nome = data.get('nome', [''])[0]
            cognome = data.get('cognome', [''])[0]
            sesso = data.get('sesso', [''])[0]
            data_nascita = data.get('data', [''])[0]
            luogo_str = data.get('luogo', [''])[0]
            
            response_data = {}

            try:
                yy, mm, dd = map(int, data_nascita.split('-'))
                cod_luogo = dizionario_luoghi.get(luogo_str)
                
                if cod_luogo:
                    cf_result = calcola_codice_fiscale(nome, cognome, dd, mm, yy, sesso, cod_luogo)
                    response_data = {'success': True, 'cf': cf_result}
                else:
                    response_data = {'success': False, 'errore': 'Luogo non valido. Selezionalo dalla lista.'}
            except Exception as e:
                response_data = {'success': False, 'errore': f'Errore nei dati: {e}'}

            # Invia la risposta JSON
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode('utf-8'))

# --- AVVIO ---
if __name__ == '__main__':
    carica_dati()
    port = 8000
    server_address = ('', port)
    httpd = HTTPServer(server_address, RequestHandler)
    
    url = f"http://127.0.0.1:{port}"
    print(f"Server attivo su {url}")
    webbrowser.open(url)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer interrotto.")
        httpd.server_close()