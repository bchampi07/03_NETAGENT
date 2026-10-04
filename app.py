"""NET AGENT 0.1 - interfaz web con Streamlit."""

import streamlit as st

from netagent import (
    ESTADO_INICIAL,
    TIPOS_EQUIPO,
    ErrorValidacion,
    agregar_conexion,
    agregar_equipo,
    comprobar_red,
    connect,
    eliminar_conexion,
    eliminar_equipo,
    generar_mapa_dot,
    listar_conexiones,
    listar_equipos,
    listar_revisiones,
    resultados_de_revision,
)

st.set_page_config(page_title="NET AGENT", page_icon="🛰️", layout="wide")
st.title("NET AGENT 0.1")
st.caption(
    "Inventario de equipos, mapa de conexiones y comprobación de conectividad "
    "mediante ping en redes autorizadas."
)


def avisar(tipo: str, texto: str) -> None:
    """Guarda un mensaje para mostrarlo tras recargar la página."""
    st.session_state["aviso"] = (tipo, texto)


def mostrar_aviso() -> None:
    aviso = st.session_state.pop("aviso", None)
    if aviso:
        getattr(st, aviso[0])(aviso[1])


def tabla_equipos(equipos) -> list:
    return [
        {
            "Nombre": e["nombre"],
            "Tipo": e["tipo"],
            "IPv4": e["ipv4"],
            "Área": e["area"],
            "Estado": e["estado"],
            "Última revisión": e["ultima_revision"] or "—",
        }
        for e in equipos
    ]


db = connect()
try:
    mostrar_aviso()
    pestanas = st.tabs(
        ["Inventario", "Mapa y conexiones", "Comprobar red", "Historial", "Cómo usarlo"]
    )
    tab_inv, tab_mapa, tab_red, tab_hist, tab_ayuda = pestanas
    equipos = listar_equipos(db)

    # ------------------------------------------------------------------ #
    with tab_inv:
        st.subheader("Registrar equipo")
        with st.form("form_equipo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre del equipo", placeholder="Mi-PC")
            tipo = c2.selectbox("Tipo", TIPOS_EQUIPO)
            c3, c4 = st.columns(2)
            ipv4 = c3.text_input("Dirección IPv4", placeholder="192.168.1.10")
            area = c4.text_input("Área o ubicación", placeholder="Laboratorio")
            enviado = st.form_submit_button("Registrar equipo")
        if enviado:
            try:
                agregar_equipo(db, nombre, tipo, ipv4, area)
                avisar("success", f"Equipo «{nombre.strip()}» registrado ({ESTADO_INICIAL}).")
                st.rerun()
            except ErrorValidacion as error:
                st.error(str(error))

        st.subheader("Equipos registrados")
        if equipos:
            st.dataframe(tabla_equipos(equipos))
            with st.expander("Eliminar un equipo"):
                por_id = {e["id"]: f'{e["nombre"]} ({e["ipv4"]})' for e in equipos}
                elegido = st.selectbox(
                    "Equipo", list(por_id), format_func=por_id.get, key="del_equipo"
                )
                if st.button("Eliminar equipo seleccionado"):
                    eliminar_equipo(db, elegido)
                    avisar("success", "Equipo eliminado.")
                    st.rerun()
        else:
            st.info("Todavía no hay equipos registrados.")

    # ------------------------------------------------------------------ #
    with tab_mapa:
        st.subheader("Registrar conexión")
        if len(equipos) < 2:
            st.info("Registre al menos dos equipos para poder crear una conexión.")
        else:
            por_id = {e["id"]: f'{e["nombre"]} ({e["ipv4"]})' for e in equipos}
            with st.form("form_conexion", clear_on_submit=True):
                c1, c2 = st.columns(2)
                eq1 = c1.selectbox("Equipo 1", list(por_id), format_func=por_id.get)
                eq2 = c2.selectbox("Equipo 2", list(por_id), format_func=por_id.get, index=1)
                descripcion = st.text_input("Descripción (opcional)", placeholder="Cable UTP")
                enviado = st.form_submit_button("Añadir conexión")
            if enviado:
                try:
                    agregar_conexion(db, eq1, eq2, descripcion)
                    avisar("success", "Conexión registrada.")
                    st.rerun()
                except ErrorValidacion as error:
                    st.error(str(error))

        conexiones = listar_conexiones(db)
        st.subheader("Mapa de red")
        if equipos:
            st.graphviz_chart(generar_mapa_dot(db))
            st.caption("Verde: responde · Rojo: no responde · Gris: sin comprobar.")
        else:
            st.info("El mapa aparecerá cuando registre equipos.")

        if conexiones:
            st.subheader("Conexiones registradas")
            st.dataframe(
                [
                    {"Equipo 1": c["equipo_a"], "Equipo 2": c["equipo_b"],
                     "Descripción": c["descripcion"] or "—"}
                    for c in conexiones
                ]
            )
            with st.expander("Eliminar una conexión"):
                por_con = {c["id"]: f'{c["equipo_a"]} — {c["equipo_b"]}' for c in conexiones}
                elegida = st.selectbox(
                    "Conexión", list(por_con), format_func=por_con.get, key="del_con"
                )
                if st.button("Eliminar conexión seleccionada"):
                    eliminar_conexion(db, elegida)
                    avisar("success", "Conexión eliminada.")
                    st.rerun()

    # ------------------------------------------------------------------ #
    with tab_red:
        st.subheader("Comprobar red")
        st.warning(
            "Use esta función solo en equipos y redes sobre los que tenga "
            "autorización. Se enviará un ping a cada equipo del inventario."
        )
        autorizado = st.checkbox(
            "Confirmo que cuento con autorización para comprobar estos equipos."
        )
        if st.button("Comprobar red"):
            if not autorizado:
                st.error("Debe marcar la confirmación de autorización.")
            elif not equipos:
                st.error("Registre al menos un equipo en la pestaña Inventario.")
            else:
                with st.spinner("Comprobando equipos..."):
                    st.session_state["ultima_revision"] = comprobar_red(db)
                st.rerun()

        revision_id = st.session_state.get("ultima_revision")
        if revision_id:
            resultados = resultados_de_revision(db, revision_id)
            responden = sum(1 for r in resultados if r["estado"] == "Responde")
            st.success(f"Revisión completada: {responden} de {len(resultados)} equipos responden.")
            st.dataframe(
                [{"Equipo": r["nombre"], "IPv4": r["ipv4"], "Estado": r["estado"]}
                 for r in resultados]
            )

    # ------------------------------------------------------------------ #
    with tab_hist:
        st.subheader("Historial de revisiones")
        revisiones = listar_revisiones(db)
        if not revisiones:
            st.info("Aún no se ha realizado ninguna revisión.")
        else:
            por_rev = {
                r["id"]: f'Revisión {r["id"]} · {r["fecha"]} · {r["respondieron"]}/{r["total"]} responden'
                for r in revisiones
            }
            elegida = st.selectbox("Revisión", list(por_rev), format_func=por_rev.get)
            for r in resultados_de_revision(db, elegida):
                with st.expander(f'{r["nombre"]} ({r["ipv4"]}) — {r["estado"]}'):
                    st.write(f'Fecha: {r["fecha"]}')
                    st.code(r["salida"] or "(sin salida)", language="text")

    # ------------------------------------------------------------------ #
    with tab_ayuda:
        st.subheader("Cómo usarlo")
        st.markdown(
            """
1. **Inventario:** registre cada equipo con su nombre, tipo, dirección IPv4 y área.
   Al inicio aparece como *Sin comprobar*.
2. **Mapa y conexiones:** una los equipos registrados para dibujar la topología.
   Las conexiones se registran manualmente.
3. **Comprobar red:** marque la confirmación de autorización y pulse
   *Comprobar red*. Cada equipo pasa a *Responde* o *No responde*.
4. **Historial:** consulte cada revisión con su fecha, estado y la salida técnica del ping.

**Importante:** NET AGENT solo envía ping a las direcciones que usted registra.
Úselo únicamente en redes y equipos autorizados.
            """
        )
finally:
    db.close()
