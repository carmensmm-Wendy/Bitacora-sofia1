@app.route("/create_today", methods=["POST"])
def create_today():
    hoy = datetime.today().strftime("%Y-%m-%d")
    print("Fecha de hoy:", hoy)

    # 1️⃣ Obtener la última hoja
    ultima_hoja = obtener_ultima_hoja()
    print("Última hoja detectada:", ultima_hoja)
    if not ultima_hoja:
        return jsonify({"error": "No se detectó ninguna hoja anterior."}), 400

    # 2️⃣ Crear nueva hoja
    requests = [{"addSheet": {"properties": {"title": hoy}}}]
    try:
        respuesta = service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID, body={"requests": requests}
        ).execute()
        print("Respuesta batchUpdate (creación de hoja):", respuesta)
    except Exception as e:
        print("Error al crear hoja:", e)
        return jsonify({"error": str(e)}), 500

    # 3️⃣ Copiar encabezados (A-H)
    try:
        encabezados = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!A1:H1"
        ).execute().get("values", [])
        print("Encabezados obtenidos:", encabezados)
    except Exception as e:
        print("Error al obtener encabezados:", e)
        return jsonify({"error": str(e)}), 500

    if encabezados:
        try:
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{hoy}!A1",
                valueInputOption="USER_ENTERED",
                body={"values": encabezados}
            ).execute()
            print("Encabezados copiados a la nueva hoja")
        except Exception as e:
            print("Error al copiar encabezados:", e)
            return jsonify({"error": str(e)}), 500

    # 4️⃣ Copiar datos de productos (B-H) y preparar fórmulas
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID, range=f"{ultima_hoja}!B2:H"
        ).execute()
        valores = result.get("values", [])
        print(f"Filas obtenidas de la última hoja: {len(valores)}")
    except Exception as e:
        print("Error al obtener datos de productos:", e)
        return jsonify({"error": str(e)}), 500

    nueva_data = []
    fila_excel = 2
    for fila in valores:
        producto = fila[0] if len(fila) >= 1 else ""
        valor_unit = fila[1] if len(fila) >= 2 else ""
        utilidad = fila[2] if len(fila) >= 3 else ""
        total_valor = ""
        unidades_vendidas = ""
        unidades_restantes = fila[5] if len(fila) >= 6 else ""
        inventario_inicial = fila[6] if len(fila) >= 7 else ""

        nueva_data.append([
            hoy,
            producto,
            valor_unit,
            utilidad,
            total_valor,
            unidades_vendidas,
            unidades_restantes,
            inventario_inicial
        ])
        fila_excel += 1

    if nueva_data:
        try:
            service.spreadsheets().values().update(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{hoy}!A2",
                valueInputOption="USER_ENTERED",
                body={"values": nueva_data}
            ).execute()
            print("Datos copiados a la nueva hoja")
        except Exception as e:
            print("Error al copiar datos:", e)
            return jsonify({"error": str(e)}), 500

    # 5️⃣ Aplicar fórmulas en E y G
    try:
        formulas_total_valor = [[f"=C{idx}*(1+D{idx}/100)*F{idx}"] for idx in range(2, fila_excel)]
        formulas_unidades_restantes = [[f"=H{idx}-F{idx}"] for idx in range(2, fila_excel)]

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!E2",
            valueInputOption="USER_ENTERED",
            body={"values": formulas_total_valor}
        ).execute()

        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{hoy}!G2",
            valueInputOption="USER_ENTERED",
            body={"values": formulas_unidades_restantes}
        ).execute()
        print("Fórmulas aplicadas")
    except Exception as e:
        print("Error al aplicar fórmulas:", e)
        return jsonify({"error": str(e)}), 500

    return redirect(url_for("index"))
