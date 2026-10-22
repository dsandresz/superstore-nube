"""Convierte la tabla plana Global Superstore en 5 tablas normalizadas."""
import hashlib
from pathlib import Path

import pandas as pd

ENTRADA = Path("datos/Global_Superstore2.csv")
SALIDA = Path("salidas")
SALIDA.mkdir(exist_ok=True)

# 1. Leer la tabla plana y registrar su huella
huella = hashlib.sha256(ENTRADA.read_bytes()).hexdigest()
df = pd.read_csv(ENTRADA, encoding="cp1252")
df["Order Date"] = pd.to_datetime(df["Order Date"], dayfirst=True)
df["Ship Date"] = pd.to_datetime(df["Ship Date"], dayfirst=True)
print(f"Tabla plana: {len(df)} filas, huella {huella[:16]}")

# 2. Claves nuevas donde las originales no son confiables
def clave(columnas, prefijo):
    """Asigna un número a cada combinación distinta de las columnas dadas."""
    codigos = df.groupby(columnas, sort=True, dropna=False).ngroup() + 1
    return prefijo + codigos.astype(str).str.zfill(6)

df["producto_id"] = clave(["Product ID", "Product Name"], "P")
df["ubicacion_id"] = clave(["City", "State", "Country", "Region", "Market"], "U")
df["orden_id"] = clave(["Order ID", "Customer ID", "Order Date"], "O")

# 3. Separar en tablas
tablas = {
    "clientes": df[["Customer ID", "Customer Name", "Segment"]]
        .drop_duplicates().rename(columns={"Customer ID": "cliente_id",
        "Customer Name": "nombre", "Segment": "segmento"}),
    "productos": df[["producto_id", "Product ID", "Product Name", "Category", "Sub-Category"]]
        .drop_duplicates().rename(columns={"Product ID": "codigo_original",
        "Product Name": "nombre", "Category": "categoria", "Sub-Category": "subcategoria"}),
    "ubicaciones": df[["ubicacion_id", "City", "State", "Country", "Region", "Market"]]
        .drop_duplicates().rename(columns={"City": "ciudad", "State": "estado",
        "Country": "pais", "Region": "region", "Market": "mercado"}),
    "ordenes": df[["orden_id", "Order ID", "Customer ID", "ubicacion_id", "Order Date",
                   "Ship Date", "Ship Mode", "Order Priority"]]
        .drop_duplicates().rename(columns={"Order ID": "codigo_original",
        "Customer ID": "cliente_id", "Order Date": "fecha_pedido", "Ship Date": "fecha_envio",
        "Ship Mode": "modo_envio", "Order Priority": "prioridad"}),
    "lineas_orden": df[["Row ID", "orden_id", "producto_id", "Sales", "Quantity",
                        "Discount", "Profit", "Shipping Cost"]]
        .rename(columns={"Row ID": "linea_id", "Sales": "ventas", "Quantity": "cantidad",
        "Discount": "descuento", "Profit": "ganancia", "Shipping Cost": "costo_envio"}),
}

# 4. Verificar que cada clave sea única y guardar
llaves = {"clientes": "cliente_id", "productos": "producto_id", "ubicaciones": "ubicacion_id",
          "ordenes": "orden_id", "lineas_orden": "linea_id"}
for nombre, tabla in tablas.items():
    assert tabla[llaves[nombre]].is_unique, f"Clave repetida en {nombre}"
    tabla.sort_values(llaves[nombre]).to_csv(SALIDA / f"{nombre}.csv", index=False)
    print(f"{nombre:13s} {len(tabla):>7,} filas")

# 5. Comprobar que no se perdió información: las ventas totales deben coincidir
total = tablas["lineas_orden"]["ventas"].sum()
assert abs(total - df["Sales"].sum()) < 1e-6
print(f"Ventas totales conservadas: {total:,.2f}")