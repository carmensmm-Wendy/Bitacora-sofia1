from flask import Flask, jsonify, render_template, request, redirect, url_for
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime
import os
import json
import re

# ================== CONFIG ==================
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = "1rYqx_j6FxJcx0txntZ5cE5LjQoE3jS9Dg6yFi5Dn50Y"  # Tu ID de Google Sheet

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

# ================== CLIENTE DE SHEETS ==================
service = build("sheets", "v4", credentials=creds)

# ================== FLASK APP ==================
app = Flask(__name__)

# ================== HELPERS ==================
def obtener_ultima_hoja():
    """Devuelve el título de la última hoja con formato YYYY-MM-DD."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = spreadsheet.get("sheets", [])
    fechas = []
    for s in sheets:
        title = s["properties"]["title"]
        if re.fullmatch(r"\d{4}-\d{1,2}-\d{1,2}", title):
            fechas.append(title)
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
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID, body={"requests": requests}
    ).execute()

    # 2) Copiar encabezados (A-H)
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

    # 3) Copiar datos de productos (B-H) y preparar nuevas filas
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!B2:H"
    ).execute()
    valores = result.get("values", [])

    nueva_data = []  # A-H
    fila_excel = 2
    for fila in valores:
        producto = fila[0] if len(fila) >= 1 else ""
        valor_unit = fila[1] if len(fila) >= 2 else ""
        utilidad = fila[2] if len(fila) >= 3 else ""
        total_valor = ""  # Se reinicia
        unidades_vendidas = ""  # Se reinicia
        unidades_restantes = fila[5] if len(fila) >= 6 else ""
        inventario_inicial = fila[6] if len(fila) >= 7 else ""

        nueva_data.append([
            hoy,           # A: fecha
            producto,      # B: producto
            valor_unit,    # C: valor unitario
            utilidad,      # D: porcentaje utilidad
            total_valor,   # E: total valor (fórmula luego)
            unidades_vendidas,  # F: unidades vendidas
            unidades_restantes, # G: unidades restantes (fórmula luego)
            inventario_inicial  # H: inventario inicial
        ])
        fila_excel += 1

    if nueva_data:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!A2",
            valueInputOption="USER_ENTERED",
            body={"values": nueva_data}
        ).execute()

    # 4) Aplicar fórmulas
    formulas_total_valor = [
        [f"=IF(F{idx}=\"\",0,C{idx}*(1+D{idx}/100)*F{idx})"]
        for idx in range(2, fila_excel)
    ]
    formulas_unidades_restantes = [
        [f"=IF(F{idx}=\"\",H{idx},H{idx}-F{idx})"]
        for idx in range(2, fila_excel)
    ]

    if formulas_total_valor:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!E2",
            valueInputOption="USER_ENTERED",
            body={"values": formulas_total_valor}
        ).execute()

    if formulas_unidades_restantes:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!G2",
            valueInputOption="USER_ENTERED",
            body={"values": formulas_unidades_restantes}
        ).execute()

    return redirect(url_for("index"))

# ================== MAIN ==================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

