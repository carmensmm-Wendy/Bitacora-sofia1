from flask import Flask, jsonify, render_template, request, redirect, url_for
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json

# ================== CONFIG ==================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1rYqx_j6FxJcx0txntZ5cE5LjQoE3jS9Dg6yFi5Dn50Y"  # Tu ID de hoja

# ================== CREDENCIALES ==================
def cargar_credenciales():
    google_creds_env = os.getenv("GOOGLE_CREDENTIALS")
    if google_creds_env:
        try:
            creds_dict = json.loads(google_creds_env)
            return Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except json.JSONDecodeError:
            raise Exception("❌ La variable de entorno GOOGLE_CREDENTIALS no contiene un JSON válido")
    raise Exception("❌ No se encontró la variable de entorno GOOGLE_CREDENTIALS")

creds = cargar_credenciales()

# ================== APP ==================
app = Flask(__name__)
service = build("sheets", "v4", credentials=creds)

# ================== HELPERS ==================
def obtener_ultima_hoja():
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get("sheets", [])
    fechas = [s["properties"]["title"] for s in sheets if s["properties"]["title"].isdigit() is False]
    if not fechas:
        return None
    fechas.sort(reverse=True)
    return fechas[0]

# ================== ROUTES ==================
@app.route("/")
def index():
    today = datetime.today().strftime("%Y-%m-%d")
    return render_template("index.html", today=today)

@app.route("/create_today", methods=["POST"])
def create_today():
    hoy = datetime.today().strftime("%Y-%m-%d")
    ultima_hoja = obtener_ultima_hoja()

    if not ultima_hoja:
        return jsonify({"error": "No existe ninguna hoja anterior con datos."}), 400

    # 1) Crear nueva hoja
    requests = [{"addSheet": {"properties": {"title": hoy}}}]
    service.spreadsheets().batchUpdate(spreadsheetId=SPREADSHEET_ID, body={"requests": requests}).execute()

    # 2) Copiar encabezados
    encabezados = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!A1:H1"
    ).execute().get("values", [])

    if encabezados:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": encabezados}
        ).execute()

    # 3) Copiar productos y datos básicos de la hoja anterior
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!B2:H"
    ).execute()
    values = result.get("values", [])

    nueva_data = []
    fila_excel = 2

    for fila in values:
        # Ajuste para que siempre tenga 7 columnas
        fila_completa = fila + [""] * (7 - len(fila))
        nueva_data.append([
            hoy,               # A: fecha actual
            fila_completa[0],  # B: producto
            fila_completa[1],  # C: valor unitario
            fila_completa[2],  # D: utilidad %
            fila_completa[3],  # E: total valor
            fila_completa[4],  # F: total unidades
            fila_completa[5],  # G: unidades restantes
            fila_completa[6],  # H: inventario inicial
        ])
        fila_excel += 1

    if nueva_data:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!A2",
            valueInputOption="USER_ENTERED",
            body={"values": nueva_data}
        ).execute()

    return redirect(url_for("index"))

# ================== MAIN ==================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

