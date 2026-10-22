"""Asistente: responde en español preguntas sobre las 5 tablas usando GLM (Z.ai) por API.

Uso:  python src/asistente_ia.py "¿Qué país pierde más dinero?"
La clave se lee de la variable de entorno ZAI_API_KEY (nunca se escribe en el código).
"""
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

import duckdb

URL = "https://api.z.ai/api/paas/v4/chat/completions"
MODELO = os.environ.get("ZAI_MODEL", "glm-4.7-flash")
SALIDAS = Path("salidas")

ESQUEMA = """
clientes(cliente_id, nombre, segmento)
productos(producto_id, codigo_original, nombre, categoria, subcategoria)
ubicaciones(ubicacion_id, ciudad, estado, pais, region, mercado)
ordenes(orden_id, codigo_original, cliente_id, ubicacion_id, fecha_pedido, fecha_envio, modo_envio, prioridad)
lineas_orden(linea_id, orden_id, producto_id, ventas, cantidad, descuento, ganancia, costo_envio)
Relaciones: lineas_orden.orden_id = ordenes.orden_id; lineas_orden.producto_id = productos.producto_id;
ordenes.cliente_id = clientes.cliente_id; ordenes.ubicacion_id = ubicaciones.ubicacion_id.
descuento va de 0 a 1 (0.2 = 20 %). Los valores de texto (pais, mercado, categoria...) están en inglés.
Mercados: APAC, EU, US, LATAM, EMEA, Africa, Canada.
Pistas importantes:
- pais, ciudad, region y mercado están SOLO en la tabla ubicaciones (se llega por ordenes.ubicacion_id).
- categoria y subcategoria están SOLO en la tabla productos.
- "Perder dinero" o "pérdida" significa ganancia negativa: usa SUM(ganancia) y ordena de menor a mayor.
- Usa solo las columnas listadas arriba.
"""


def preguntar_a_glm(mensaje_sistema, mensaje_usuario):
    """Envía un mensaje a GLM y devuelve el texto de la respuesta."""
    clave = os.environ.get("ZAI_API_KEY")
    if not clave:
        sys.exit("Falta la clave: define ZAI_API_KEY como secreto de Codespaces o con export.")
    cuerpo = {
        "model": MODELO,
        "messages": [{"role": "system", "content": mensaje_sistema},
                     {"role": "user", "content": mensaje_usuario}],
        "temperature": 0.1,
        "thinking": {"type": "disabled"},
    }
    peticion = urllib.request.Request(
        URL, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"Authorization": f"Bearer {clave}", "Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=120) as respuesta:
        datos = json.load(respuesta)
    return datos["choices"][0]["message"]["content"].strip()


def extraer_sql(texto):
    """Quita los ``` que a veces agrega el modelo y deja solo la consulta."""
    texto = re.sub(r"```(sql)?", "", texto, flags=re.IGNORECASE).strip()
    return texto.rstrip(";")


def main():
    pregunta = " ".join(sys.argv[1:]) or "¿Qué mercado tiene el peor margen de ganancia?"
    print(f"Pregunta: {pregunta}\n")

    # 1. Cargar las tablas normalizadas
    con = duckdb.connect()
    for tabla in ["clientes", "productos", "ubicaciones", "ordenes", "lineas_orden"]:
        con.execute(f"CREATE TABLE {tabla} AS SELECT * FROM read_csv_auto('{SALIDAS / tabla}.csv')")

    # 2 y 3. La IA traduce la pregunta a SQL y se ejecuta; si falla, la IA corrige su error
    instrucciones = ("Eres un analista de datos. Convierte la pregunta en UNA consulta SQL para DuckDB "
                     "sobre estas tablas. Responde solo con el SQL, sin explicaciones.\n" + ESQUEMA)
    mensaje = pregunta
    for intento in range(1, 4):
        sql = extraer_sql(preguntar_a_glm(instrucciones, mensaje))
        print(f"SQL generado por la IA (intento {intento}):\n{sql}\n")
        if not sql.lower().lstrip("( \n").startswith(("select", "with")):
            sys.exit("La IA no devolvió una consulta de lectura.")
        try:
            resultado = con.execute(sql).df().head(20)
            break
        except duckdb.Error as error:
            print(f"La consulta falló: {str(error).splitlines()[0]}\nSe le pide a la IA que la corrija...\n")
            mensaje = (f"Pregunta: {pregunta}\nTu consulta anterior:\n{sql}\n"
                       f"dio este error:\n{error}\nEscribe la consulta corregida.")
    else:
        sys.exit("La IA no logró una consulta válida en 3 intentos. Prueba a redactar la pregunta de otra forma.")
    print(f"Resultado:\n{resultado.to_string(index=False)}\n")

    # 4. La IA explica el resultado en español
    explicacion = preguntar_a_glm(
        "Eres un analista de datos. Explica el resultado en español, en máximo 3 frases claras, "
        "para alguien sin conocimientos técnicos. Usa solo los números del resultado.",
        f"Pregunta: {pregunta}\nSQL: {sql}\nResultado:\n{resultado.to_string(index=False)}")
    print(f"Respuesta de la IA:\n{explicacion}")


if __name__ == "__main__":
    main()
