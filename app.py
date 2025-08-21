from flask import Flask, jsonify, render_template, request, redirect, url_for
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json
import re

# ================== CONFIG ==================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1OzbbXYOoJbco7pM21ook6BSFs-gztSFocZBTip-D3KA"

# ================== CREDENCIALES ==================
google_creds_env = os.getenv("GOOGLE_CREDENTIALS")
if not google_creds_env:
    raise Exception("❌ No se encontró la variable de entorno GOOGLE_CREDENTIALS")

try:
    creds_dict = json.loads(google_creds_env)
    creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
except json.JSONDecodeError:
    raise Exception("❌ La variable de entorno GOOGLE_CREDENTIALS no contiene un JSON válido")

# Crea la app de Flask
app = Flask(__name__)

# Crea el cliente de Google Sheets
service = build("sheets", "v4", credentials=creds)

# ================== HELPERS ==================
def obtener_ultima_hoja():
    """Devuelve el título de la última hoja con formato YYYY-MM-DD."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get("sheets", [])
    fechas = [s["properties"]["title"] for s in sheets if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["properties"]["title"])]
    return max(fechas) if fechas else None

# ================== ROUTES ==================
@app.route("/")
def index():
    today = datetime.today().strftime("%Y-%m-%d")
    return render_template("index.html", today=today)

@app.route("/create_today", methods=["POST"])
def create_today():
    hoy = datetime.today().strftime("%Y-%m-%d")
    ultima_hoja = obtener_ultima_hoja()
    mes_actual = datetime.today().strftime("%Y-%m")

    if not ultima_hoja:
        return jsonify({"error": "No existe ninguna hoja anterior con datos."}), 400

    # Crear nueva hoja
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"addSheet": {"properties": {"title": hoy}}}]}
    ).execute()

    # Copiar encabezados
    encabezados = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!A1:G1"
    ).execute().get("values", [])

    if encabezados:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": encabezados}
        ).execute()

    # Copiar base A-B dejando C,D,E vacías
    values = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!A2:B"
    ).execute().get("values", [])

    nueva_data, formulas_f, formulas_g = [], [], []
    fila_excel = 2

    for fila in values:
        if len(fila) >= 2:
            nueva_data.append([hoy, fila[1], "", "", ""])
            formulas_f.append([f"='{ultima_hoja}'!F{fila_excel} + C{fila_excel}*(1+D{fila_excel}/100) - E{fila_excel}"])
            if mes_actual == ultima_hoja[:7]:
                formulas_g.append([f"='{ultima_hoja}'!G{fila_excel} + C{fila_excel}"])
            else:
                formulas_g.append([f"C{fila_excel}"])
            fila_excel += 1

    if nueva_data:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=f"{hoy}!A2",
            valueInputOption="USER_ENTERED", body={"values": nueva_data}
        ).execute()

    if formulas_f:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=f"{hoy}!F2",
            valueInputOption="USER_ENTERED", body={"values": formulas_f}
        ).execute()

    if formulas_g:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID, range=f"{hoy}!G2",
            valueInputOption="USER_ENTERED", body={"values": formulas_g}
        ).execute()

    return redirect(url_for("index"))

# ================== MAIN ==================
if __name__ == "__main__":
    # Render usará Gunicorn, esto solo sirve localmente
    app.run(debug=True, host="0.0.0.0", port=5000)
