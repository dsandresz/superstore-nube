"""Responde la pregunta del proyecto con consultas SQL sobre las 5 tablas normalizadas."""
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

SALIDAS = Path("salidas")
con = duckdb.connect()

# Cargar las 5 tablas que produjo normalizar.py
for tabla in ["clientes", "productos", "ubicaciones", "ordenes", "lineas_orden"]:
    con.execute(f"CREATE TABLE {tabla} AS SELECT * FROM read_csv_auto('{SALIDAS / tabla}.csv')")

CONSULTAS = {
    "1_descuento": """
        SELECT CASE WHEN descuento = 0    THEN '1. Sin descuento'
                    WHEN descuento <= 0.1 THEN '2. Hasta 10 %'
                    WHEN descuento <= 0.2 THEN '3. Hasta 20 %'
                    WHEN descuento <= 0.3 THEN '4. Hasta 30 %'
                    ELSE '5. Más de 30 %' END            AS rango_descuento,
               COUNT(*)                                  AS lineas,
               ROUND(SUM(ventas))                        AS ventas,
               ROUND(SUM(ganancia))                      AS ganancia,
               ROUND(100 * SUM(ganancia) / SUM(ventas), 1) AS margen_pct,
               ROUND(100 * AVG(CASE WHEN ganancia < 0 THEN 1 ELSE 0 END), 1) AS pct_lineas_con_perdida
        FROM lineas_orden
        GROUP BY 1 ORDER BY 1""",
    "2_mercado": """
        SELECT u.mercado,
               ROUND(SUM(l.ventas))                          AS ventas,
               ROUND(SUM(l.ganancia))                        AS ganancia,
               ROUND(100 * SUM(l.ganancia) / SUM(l.ventas), 1) AS margen_pct,
               ROUND(100 * AVG(l.descuento), 1)              AS descuento_promedio_pct
        FROM lineas_orden l
        JOIN ordenes o     ON l.orden_id = o.orden_id
        JOIN ubicaciones u ON o.ubicacion_id = u.ubicacion_id
        GROUP BY 1 ORDER BY margen_pct""",
    "3_peores_combinaciones": """
        SELECT u.mercado, p.subcategoria,
               ROUND(SUM(l.ganancia))             AS ganancia,
               ROUND(100 * AVG(l.descuento), 1)   AS descuento_promedio_pct
        FROM lineas_orden l
        JOIN ordenes o     ON l.orden_id = o.orden_id
        JOIN ubicaciones u ON o.ubicacion_id = u.ubicacion_id
        JOIN productos p   ON l.producto_id = p.producto_id
        GROUP BY 1, 2 ORDER BY ganancia LIMIT 10""",
}

for nombre, sql in CONSULTAS.items():
    resultado = con.execute(sql).df()
    resultado.to_csv(SALIDAS / f"resultado_{nombre}.csv", index=False)
    print(f"\n=== {nombre} ===")
    print(resultado.to_string(index=False))

# Gráfico para el póster: margen de ganancia según el descuento
d = con.execute(CONSULTAS["1_descuento"]).df()
etiquetas = [r.split(". ", 1)[1] for r in d["rango_descuento"]]
colores = ["#1b7837" if m >= 0 else "#b2182b" for m in d["margen_pct"]]

fig, ax = plt.subplots(figsize=(8, 4.5))
barras = ax.bar(etiquetas, d["margen_pct"], color=colores)
ax.axhline(0, color="black", linewidth=0.8)
ax.set_ylim(d["margen_pct"].min() * 1.2, d["margen_pct"].max() * 1.25)
ax.bar_label(barras, labels=[f"{m:.1f} %" for m in d["margen_pct"]], padding=3)
ax.set_title("Margen de ganancia según el nivel de descuento")
ax.set_ylabel("Ganancia / ventas (%)")
ax.spines[["top", "right"]].set_visible(False)
fig.tight_layout()
fig.savefig(SALIDAS / "grafico_descuento.png", dpi=200)
print("\nGráfico guardado en salidas/grafico_descuento.png")
