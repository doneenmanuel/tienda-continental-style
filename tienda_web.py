import streamlit as st
import sqlite3
import os
from datetime import datetime
import hashlib
import uuid
import urllib.parse
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO

# ==================================================
# 📁 CREAR CARPETA DE FOTOS SI NO EXISTE
# ==================================================
if not os.path.exists("fotos_productos"):
    os.makedirs("fotos_productos")

# ==================================================
# 🏷️ DATOS DE TU TIENDA
# ==================================================
NOMBRE_TIENDA = "CONTINENTAL STYLE"
TAGLINE = "Estilo que Cruza Fronteras — Europa y América"
TU_DIRECCION = "San Cristóbal, Rep. Dominicana"
TU_TELEFONO = "+1 849-244-1606"
TU_WHATSAPP = "+18492441606"
HORARIO = "Lunes a Sábado: 8:00 AM – 7:00 PM"

DATOS_BANCOS = """
🏦 **BANCO POPULAR** — Corriente
📄 Cuenta: 852145473

🏦 **BHD** — Ahorro
📄 Cuenta: 23371450016

🏦 **RESERVAS** — Ahorro
📄 Cuenta: 9608001050

💳 **QICK** — En Pesos
📄 Cuenta: 1007543413

👤 **Titular:** Enmanuel Done Martinez
📄 **Cédula:** 402-2556390-3
"""

LOGO_HTML = f"""
<div style='text-align:center; padding:20px 0;'>
    <h1 style='font-size:36px; font-weight:800; background:linear-gradient(90deg, #f59e0b, #fbbf24); -webkit-background-clip:text; -webkit-text-fill-color:text;'>🌍 {NOMBRE_TIENDA}</h1>
    <p style='color:#94a3b8; font-size:16px;'>{TAGLINE}</p>
    <hr style='border:none; height:2px; background:linear-gradient(90deg, transparent, #f59e0b, transparent); margin:20px 0;'>
</div>
"""

# ==================================================
# 🔐 FUNCIONES DE SEGURIDAD
# ==================================================
def cifrar_contraseña(contraseña: str) -> str:
    return hashlib.sha256(contraseña.encode()).hexdigest()

def generar_id_usuario() -> str:
    return str(uuid.uuid4())[:8]

# ==================================================
# 🗄️ CONEXIÓN BASE DE DATOS
# ==================================================
def conectar():
    return sqlite3.connect("tienda.db")

# ==================================================
# 🗄️ INICIALIZAR BASE DE DATOS — COLUMNA ETIQUETA INCLUIDA ✅
# ==================================================
def inicializar_base_datos():
    conn = conectar()
    c = conn.cursor()
    
    # Tabla usuarios
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario TEXT PRIMARY KEY,
            correo TEXT UNIQUE NOT NULL,
            contraseña TEXT NOT NULL,
            nombre TEXT,
            estado TEXT DEFAULT 'pendiente',
            es_admin INTEGER DEFAULT 0,
            fecha_registro TEXT
        )
    """)
    
    # Tabla productos_tienda — CON COLUMNA ETIQUETA ✅
    c.execute("""
        CREATE TABLE IF NOT EXISTS productos_tienda (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_usuario TEXT,
            nombre TEXT,
            categoria TEXT,
            descripcion TEXT,
            precio_costo REAL,
            precio_venta REAL,
            descuento REAL DEFAULT 0,
            stock INTEGER,
            tallas TEXT,
            foto TEXT,
            etiqueta TEXT,
            FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
        )
    """)
    
    # ✅ AGREGAR COLUMNA ETIQUETA SI NO EXISTE (para productos viejos)
    try:
        c.execute("ALTER TABLE productos_tienda ADD COLUMN etiqueta TEXT")
    except:
        pass
    
    # Tabla pedidos
    c.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id_pedido INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura TEXT UNIQUE,
            nombre_cliente TEXT,
            telefono TEXT,
            direccion TEXT,
            metodo_pago TEXT,
            total REAL,
            productos TEXT,
            estado TEXT DEFAULT 'PENDIENTE',
            fecha_pedido TEXT
        )
    """)
    
    # Tabla abonos
    c.execute("""
        CREATE TABLE IF NOT EXISTS abonos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero_factura TEXT,
            descripcion TEXT,
            valor REAL,
            porcentaje REAL,
            fecha TEXT,
            FOREIGN KEY (numero_factura) REFERENCES pedidos(numero_factura)
        )
    """)
    
    # Crear ADMIN si no existe
    c.execute("SELECT * FROM usuarios WHERE es_admin = 1")
    if not c.fetchone():
        c.execute("""
            INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ("admin-001", "admin@continentalstyle.com", cifrar_contraseña("1234"), "ADMINISTRADOR", "aprobado", 1, datetime.now().strftime("%d/%m/%Y %H:%M")))
    
    conn.commit()
    conn.close()

# ==================================================
# 📊 CALCULAR ESTADÍSTICAS
# ==================================================
def calcular_estadisticas():
    conn = conectar()
    c = conn.cursor()
    c.execute("SELECT COUNT(*), SUM(precio_costo), SUM(precio_venta), SUM(stock) FROM productos_tienda")
    res = c.fetchone()
    total_prod = res[0] or 0
    inversion = res[1] or 0
    valor = res[2] or 0
    c.execute("SELECT SUM(total) FROM pedidos WHERE estado = 'PAGADO'")
    vendido = c.fetchone()[0] or 0
    c.execute("SELECT COUNT(*) FROM pedidos WHERE estado = 'PENDIENTE' OR estado = 'ABONANDO'")
    pendientes = c.fetchone()[0] or 0
    conn.close()
    ganancia = valor - inversion
    porcentaje = (ganancia / inversion * 100) if inversion > 0 else 0
    return {
        "productos": total_prod,
        "inversion": inversion,
        "valor": valor,
        "ganancia": ganancia,
        "porcentaje": porcentaje,
        "pendientes": pendientes
    }

# ==================================================
# 🛒 CARRITO — AGREGAR PRODUCTO
# ==================================================
def agregar_al_carrito(producto):
    idp, nom, pv, dsc, stk, fot, etiq = producto
    if "carrito" not in st.session_state:
        st.session_state.carrito = []
    for item in st.session_state.carrito:
        if item["id"] == idp:
            if item["cantidad"] < stk:
                item["cantidad"] += 1
            return
    st.session_state.carrito.append({
        "id": idp, "nombre": nom, "precio": pv, "cantidad": 1, "foto": fot
    })

# ==================================================
# 📄 GENERAR FACTURA PDF
# ==================================================
def generar_factura_pdf(num_fac, cliente, tel, dirc, productos, total, abonos=None, estado="PENDIENTE"):
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    w, h = letter
    
    # Encabezado
    c.setFont("Helvetica-Bold", 22)
    c.drawCentredString(w/2, h-60, "🌍 CONTINENTAL STYLE")
    c.setFont("Helvetica", 12)
    c.drawCentredString(w/2, h-85, "Estilo que Cruza Fronteras — Europa y América")
    c.drawCentredString(w/2, h-105, f"📄 FACTURA N° {num_fac}")
    c.line(50, h-120, w-50, h-120)
    
    # Datos cliente
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, h-150, "DATOS DEL CLIENTE")
    c.setFont("Helvetica", 10)
    c.drawString(50, h-170, f"Nombre: {cliente}")
    c.drawString(50, h-188, f"Teléfono: {tel}")
    c.drawString(50, h-206, f"Dirección: {dirc}")
    c.drawString(50, h-224, f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawString(50, h-242, f"Estado: {estado}")
    
    # Tabla productos
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, h-280, "PRODUCTO")
    c.drawString(280, h-280, "CANT.")
    c.drawString(350, h-280, "PRECIO")
    c.drawString(450, h-280, "SUBTOTAL")
    c.line(50, h-290, w-50, h-290)
    
    y = h-310
    c.setFont("Helvetica", 10)
    for p in productos:
        c.drawString(50, y, p["nombre"][:35])
        c.drawString(290, y, str(p["cantidad"]))
        c.drawString(355, y, f"RD$ {p['precio']:,.0f}")
        c.drawString(455, y, f"RD$ {p['precio']*p['cantidad']:,.0f}")
        y -= 22
        if y < 100:
            c.showPage()
            y = h-100
    
    # Total
    c.line(50, y, w-50, y)
    y -= 25
    c.setFont("Helvetica-Bold", 14)
    c.drawString(350, y, f"TOTAL: RD$ {total:,.0f}")
    
    # Abonos
    if abonos and len(abonos) > 0:
        y -= 40
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "HISTORIAL DE ABONOS")
        c.line(50, y-10, w-50, y-10)
        y -= 30
        c.setFont("Helvetica", 10)
        tot_ab = 0
        for a in abonos:
            c.drawString(50, y, f"{a['fecha']} — {a['descripcion']}")
            c.drawString(450, y, f"RD$ {a['valor']:,.0f}")
            tot_ab += a["valor"]
            y -= 22
        c.drawString(50, y, f"Total Abonado: RD$ {tot_ab:,.0f}")
        c.drawString(350, y, f"Saldo: RD$ {total - tot_ab:,.0f}")
    
    # Pie
    c.setFont("Helvetica", 8)
    c.drawCentredString(w/2, 40, f"📲 WhatsApp: +1 849-244-1606 | 📍 San Cristóbal, Rep. Dominicana")
    c.drawCentredString(w/2, 25, "© 2026 CONTINENTAL STYLE — Todos los derechos reservados")
    
    c.save()
    buffer.seek(0)
    return buffer.read()# ==================================================
# 🎨 ESTILO PREMIUM COMPLETO
# ==================================================
st.set_page_config(
    page_title="CONTINENTAL STYLE — Estilo que Cruza Fronteras",
    page_icon="🌍",
    layout="wide"
)
# ==================================================
# 📱 AJUSTES DE DISEÑO RESPONSIVO — CELULAR
# ==================================================
st.markdown("""
<style>
/* Títulos que no se rompan en celular */
@media (max-width: 768px) {
    h1, h2, .big-title {
        font-size: 2rem !important;
        line-height: 1.2 !important;
        text-align: center !important;
        word-break: keep-all !important;
    }
    .welcome-box {
        padding: 1.5rem !important;
    }
    /* Botones más cómodos en celular */
    .stButton > button, a[href*="wa.me"] {
        font-size: 1rem !important;
        padding: 0.6rem 1.2rem !important;
        min-height: 48px !important;
    }
}
/* Nunca cortar palabras */
* {
    word-break: keep-all !important;
    overflow-wrap: break-word !important;
}
</style>
""", unsafe_allow_html=True)
# ==================================================
# 📱 DISEÑO QUE SE VE BIEN EN CELULAR Y COMPUTADORA
# ==================================================
st.markdown("""
<style>
/* Que nada se salga de la pantalla */
* {
    box-sizing: border-box;
    max-width: 100% !important;
}

/* Espaciado limpio */
.block-container {
    padding: 1rem 1.2rem;
}

/* En celular: columnas se ponen una debajo de otra */
@media only screen and (max-width: 768px) {
    .block-container {
        padding: 1rem !important;
    }
    div[data-testid="column"] {
        width: 100% !important;
        flex: unset !important;
        margin-bottom: 1.2rem;
    }
    /* Botones más grandes para tocar con el dedo */
    button {
        width: 100% !important;
        min-height: 50px;
        font-size: 16px !important;
    }
    /* Letras cómodas de leer */
    h1 { font-size: 1.7rem !important; }
    h2 { font-size: 1.4rem !important; }
    p, label { font-size: 15px !important; }
}

/* Tarjetas de producto bonitas */
.tarjeta-producto {
    border: 1px solid #e5e5e5;
    border-radius: 14px;
    padding: 1rem;
    background: white;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
    margin-bottom: 1rem;
}
.tarjeta-producto:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    transition: 0.3s;
}

/* Imágenes bien alineadas */
img {
    object-fit: cover;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;500;600;700;800&display=swap');
        
        * { font-family: 'Poppins', sans-serif; }
        
        .stApp {
            background: linear-gradient(180deg, #020617 0%, #0f172a 40%, #1e293b 100%);
            color: #f8fafc;
        }
        
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #1e293b, #0f172a);
            border-right: 1px solid #334155;
        }
        
        .banner-principal {
            background: linear-gradient(135deg, rgba(12,32,60,0.95), rgba(15,53,112,0.9));
            border: 1px solid rgba(245,158,11,0.2);
            border-radius: 24px;
            padding: 50px 40px;
            margin-bottom: 40px;
            text-align: center;
            position: relative;
            overflow: hidden;
        }
        .banner-principal::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: radial-gradient(circle at 20% 20%, rgba(245,158,11,0.08), transparent 50%),
                        radial-gradient(circle at 80% 80%, rgba(59,130,246,0.08), transparent 50%);
            pointer-events: none;
        }
        .banner-titulo {
            font-size: 42px;
            font-weight: 800;
            background: linear-gradient(90deg, #f59e0b, #fbbf24, #f59e0b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 12px;
        }
        .banner-subtitulo {
            font-size: 18px;
            color: #e2e8f0;
            margin-bottom: 25px;
        }
        
        .fila-garantias {
            display: flex;
            flex-wrap: wrap;
            gap: 15px;
            margin: 35px 0;
        }
        .tarjeta-garantia {
            background: linear-gradient(145deg, rgba(16,185,129,0.08), rgba(16,185,129,0.03));
            border: 1px solid rgba(16,185,129,0.2);
            border-radius: 14px;
            padding: 18px 22px;
            text-align: center;
            flex: 1;
            min-width: 140px;
        }
        .garantia-icono { font-size: 28px; margin-bottom: 8px; }
        .garantia-texto { font-size: 14px; color: #bbf7d0; font-weight: 500; }
        
        .tarjeta-producto {
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border-radius: 20px;
            padding: 24px;
            margin: 12px 0;
            border: 1px solid rgba(245,158,11,0.08);
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            transition: all 0.35s ease;
            height: 100%;
            position: relative;
            overflow: hidden;
        }
        .tarjeta-producto:hover {
            transform: translateY(-6px);
            border-color: rgba(245,158,11,0.35);
            box-shadow: 0 18px 50px rgba(245,158,11,0.15);
        }
        .etiqueta-producto {
            position: absolute;
            top: 15px;
            left: 15px;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            z-index: 2;
        }
        .etiqueta-nuevo { background: linear-gradient(90deg, #3b82f6, #1d4ed8); color: white; }
        .etiqueta-oferta { background: linear-gradient(90deg, #ef4444, #dc2626); color: white; }
        .nombre-producto {
            font-size: 20px;
            font-weight: 600;
            color: #f8fafc;
            margin: 12px 0 8px 0;
        }
        .precio {
            font-size: 32px;
            font-weight: 700;
            background: linear-gradient(90deg, #f59e0b, #fbbf24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .precio-descuento {
            font-size: 16px;
            color: #f87171;
            text-decoration: line-through;
            margin-right: 10px;
        }
        .info-dato {
            font-size: 14px;
            color: #cbd5e1;
            margin: 4px 0;
        }
        .etiqueta-tallas {
            display: inline-block;
            background: rgba(59,130,246,0.15);
            color: #93c5fd;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            margin-top: 10px;
        }
        .descripcion {
            font-size: 14px;
            color: #94a3b8;
            margin-top: 12px;
            line-height: 1.5;
        }
        .alerta-stock {
            background: rgba(239,68,68,0.12);
            border: 1px solid rgba(239,68,68,0.35);
            border-radius: 10px;
            padding: 8px 12px;
            color: #fca5a5;
            font-size: 13px;
            margin-top: 10px;
        }
        .seccion-nosotros {
            background: linear-gradient(145deg, rgba(30,64,175,0.08), rgba(15,23,42,0.9));
            border: 1px solid rgba(59,130,246,0.2);
            border-radius: 20px;
            padding: 35px;
            margin: 50px 0;
        }
        .nosotros-titulo {
            font-size: 24px;
            font-weight: 700;
            color: #f59e0b;
            margin-bottom: 15px;
        }
        .nosotros-texto {
            font-size: 16px;
            color: #e2e8f0;
            line-height: 1.7;
        }
        .footer-completo {
            background: linear-gradient(180deg, #0f172a, #020617);
            border-top: 1px solid rgba(51,65,85,0.6);
            padding: 45px 30px 25px 30px;
            margin-top: 60px;
            border-radius: 24px 24px 0 0;
        }
        .footer-columna h4 { color: #f59e0b; font-size: 16px; margin-bottom: 15px; }
        .footer-columna p { color: #94a3b8; font-size: 14px; line-height: 1.8; margin: 5px 0; }
        .footer-pagos { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
        .pago-icono { background: rgba(59,130,246,0.1); padding: 6px 12px; border-radius: 8px; font-size: 13px; color: #93c5fd; }
        .caja-bancaria {
            background: linear-gradient(145deg, rgba(30,64,175,0.12), rgba(30,41,59,0.95));
            border: 1px solid rgba(59,130,246,0.3);
            border-radius: 16px;
            padding: 25px;
            margin-top: 15px;
        }
        .btn-whatsapp-grande {
            background: linear-gradient(90deg, #25d366, #128c7e);
            color: white !important;
            font-size: 18px !important;
            font-weight: 700 !important;
            padding: 16px 32px !important;
            border-radius: 14px !important;
            border: none !important;
            box-shadow: 0 6px 24px rgba(37,211,102,0.35);
            width: 100%;
            text-align: center;
            display: block;
            text-decoration: none;
            margin-top: 15px;
        }
        .tarjeta-dato {
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border-radius: 16px;
            padding: 24px;
            text-align: center;
            border: 1px solid rgba(245,158,11,0.1);
        }
        .numero-grande {
            font-size: 36px;
            font-weight: 700;
            background: linear-gradient(90deg, #f59e0b, #fbbf24);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .badge-admin { background: linear-gradient(90deg, #ef4444, #dc2626); color: white; padding: 5px 14px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-pendiente { background: linear-gradient(90deg, #f59e0b, #d97706); color: white; padding: 5px 14px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-abonando { background: linear-gradient(90deg, #3b82f6, #2563eb); color: white; padding: 5px 14px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-pagado { background: linear-gradient(90deg, #10b981, #059669); color: white; padding: 5px 14px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        hr {
            border: none;
            height: 2px;
            background: linear-gradient(90deg, transparent, rgba(245,158,11,0.4), transparent);
            margin: 40px 0;
        }
        .whatsapp-fijo {
            position: fixed;
            bottom: 25px;
            right: 25px;
            z-index: 9999;
        }
    </style>
""", unsafe_allow_html=True)

# 🟢 WHATSAPP FLOTANTE
st.markdown(f"""
<div class='whatsapp-fijo'>
    <a href='https://wa.me/{TU_WHATSAPP.replace("+","")}' target='_blank' style='
        background: linear-gradient(90deg, #25d366, #128c7e);
        color: white;
        font-size: 15px;
        font-weight: 700;
        padding: 14px 22px;
        border-radius: 50px;
        text-decoration: none;
        box-shadow: 0 4px 20px rgba(37,211,102,0.4);
    '>📲 WhatsApp</a>
</div>
""", unsafe_allow_html=True)

# ==================================================
# 🚀 INICIALIZAR SESIONES
# ==================================================
if "carrito" not in st.session_state:
    st.session_state.carrito = []
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "es_admin" not in st.session_state:
    st.session_state.es_admin = False
if "panel_admin" not in st.session_state:
    st.session_state.panel_admin = False
if "mostrar_login" not in st.session_state:
    st.session_state.mostrar_login = False
if "comprar" not in st.session_state:
    st.session_state.comprar = False
if "cambiar_clave" not in st.session_state:
    st.session_state.cambiar_clave = False

# 🗄️ INICIALIZAR BASE DE DATOS
inicializar_base_datos()

# ==================================================
# 🏪 TIENDA PÚBLICA — PÁGINA PRINCIPAL
# ==================================================
def pagina_tienda_publica():
    st.markdown(LOGO_HTML, unsafe_allow_html=True)

    # 🖼️ BANNER PRINCIPAL
    st.markdown(f"""
    <div class='banner-principal'>
        <h1 class='banner-titulo'>¡Bienvenidos a {NOMBRE_TIENDA}! 🌍</h1>
        <p class='banner-subtitulo'>{TAGLINE}</p>
    </div>
    """, unsafe_allow_html=True)

    # ⭐ GARANTÍAS
    st.markdown("""
    <div class='fila-garantias'>
        <div class='tarjeta-garantia'><div class='garantia-icono'>✅</div><div class='garantia-texto'>Productos Originales</div></div>
        <div class='tarjeta-garantia'><div class='garantia-icono'>🚚</div><div class='garantia-texto'>Envío a Todo el País</div></div>
        <div class='tarjeta-garantia'><div class='garantia-icono'>🔄</div><div class='garantia-texto'>Cambios y Devoluciones</div></div>
        <div class='tarjeta-garantia'><div class='garantia-icono'>💬</div><div class='garantia-texto'>Atención Personalizada</div></div>
    </div>
    """, unsafe_allow_html=True)

    # 📂 CATEGORÍAS
    st.markdown("### 📂 Categorías")
    categorias = ["Todas", "Calzado 👟", "Ropa Hombre 👔", "Ropa Mujer 👗", "Niños 👶", "Accesorios 🧢", "Perfumes 💎"]
    cat_sel = st.selectbox("Selecciona categoría:", categorias, label_visibility="collapsed")
    cat_limpia = cat_sel.split(" ")[0] if cat_sel != "Todas" else "Todas"

    # 🔍 BUSCADOR
    st.markdown("### 🔍 Encuentra tu estilo")
    col_b1, col_b2 = st.columns([4, 2])
    with col_b1: busqueda = st.text_input("Buscar:", placeholder="Nombre, marca, descripción...", label_visibility="collapsed")
    with col_b2: orden = st.selectbox("", ["Más recientes", "Precio: Menor → Mayor", "Precio: Mayor → Menor"], label_visibility="collapsed")

    st.markdown("<hr>", unsafe_allow_html=True)

    # 🛒 CARRITO EN BARRA LATERAL
    with st.sidebar.expander("🛒 Tu Carrito", expanded=len(st.session_state.carrito) > 0):
        if not st.session_state.carrito:
            st.info("🛍️ Tu carrito está vacío")
        else:
            total = 0
            for i, item in enumerate(st.session_state.carrito):
                subt = item["precio"] * item["cantidad"]
                total += subt
                st.write(f"**{item['nombre']}**")
                st.write(f"{item['cantidad']} × RD$ {item['precio']:.0f} = **RD$ {subt:.0f}**")
                if st.button(f"❌ Quitar", key=f"del_{i}"):
                    st.session_state.carrito.pop(i)
                    st.rerun()
                st.divider()
            st.markdown(f"### 💰 Total: **RD$ {total:.0f}**")
            if st.button("🛒 Comprar", type="primary", use_container_width=True):
                st.session_state.comprar = True
                st.rerun()
            if st.button("🗑️ Vaciar", use_container_width=True):
                st.session_state.carrito = []
                st.rerun()

    # 🔐 ACCESO ADMINISTRADOR — SIEMPRE VISIBLE EN BARRA LATERAL ✅
    with st.sidebar:
        st.markdown("---")
        if not st.session_state.usuario:
            if st.button("🔐 Acceso Administrador", use_container_width=True, type="primary"):
                st.session_state.mostrar_login = True
                st.rerun()
        else:
            st.markdown(f"### 👤 {st.session_state.usuario['nombre']}")
            if st.session_state.es_admin:
                st.markdown("<span class='badge-admin'>👑 ADMINISTRADOR</span>", unsafe_allow_html=True)
            st.markdown("---")
            if st.button("⚙️ Panel de Control", use_container_width=True, type="primary"):
                st.session_state.panel_admin = True
                st.rerun()
            if st.button("🚪 Cerrar Sesión", use_container_width=True):
                st.session_state.usuario = None
                st.session_state.es_admin = False
                st.session_state.panel_admin = False
                st.rerun()
        st.markdown("---")

    # ✅ FORMULARIO DE COMPRA
    if st.session_state.get("comprar") and st.session_state.carrito:
        st.subheader("📋 Completar tu compra")
        with st.form("form_compra"):
            c1, c2 = st.columns(2)
            with c1: nom = st.text_input("👤 Nombre Completo *")
            with c2: tel = st.text_input("📞 Teléfono / WhatsApp *")
            dirc = st.text_input("📍 Dirección de Entrega *")
            pago = st.selectbox("💳 Método de Pago *", ["💵 Efectivo al recibir", "🏦 Transferencia Bancaria", "📱 WhatsApp / Pago Móvil"])
            
            total_final = sum(i["precio"] * i["cantidad"] for i in st.session_state.carrito)
            st.markdown(f"### 💰 TOTAL A PAGAR: **RD$ {total_final:,.0f}**")
            
            if "Transferencia" in pago:
                st.markdown("<div class='caja-bancaria'>", unsafe_allow_html=True)
                st.markdown(DATOS_BANCOS)
                st.markdown("</div>", unsafe_allow_html=True)
                st.info("📸 Envía el comprobante por WhatsApp después de pagar")
            elif "WhatsApp" in pago:
                msj = f"Hola! Quiero comprar en {NOMBRE_TIENDA}:\n\n"
                for it in st.session_state.carrito:
                    msj += f"✅ {it['nombre']} × {it['cantidad']} = RD$ {it['precio']*it['cantidad']:.0f}\n"
                msj += f"\n💰 TOTAL: RD$ {total_final:,.0f}\n\n👤 {nom}\n📞 {tel}\n📍 {dirc}"
                link = f"https://wa.me/{TU_WHATSAPP.replace('+','')}?text={urllib.parse.quote(msj)}"
                st.markdown(f"<a href='{link}' target='_blank' class='btn-whatsapp-grande'>📲 ENVIAR PEDIDO POR WHATSAPP</a>", unsafe_allow_html=True)
            
            confirmar = st.form_submit_button("✅ CONFIRMAR COMPRA", type="primary", use_container_width=True)
            if confirmar:
                if not nom or not tel or not dirc:
                    st.error("⚠️ Completa todos los campos obligatorios (*)")
                else:
                    conn = conectar()
                    c = conn.cursor()
                    c.execute("SELECT COUNT(*) FROM pedidos")
                    num = str(c.fetchone()[0] + 1).zfill(8)
                    num_fac = f"FAC-{num}"
                    productos_json = str(st.session_state.carrito)
                    c.execute("""
                        INSERT INTO pedidos
                        (numero_factura, nombre_cliente, telefono, direccion, metodo_pago, total, productos, estado, fecha_pedido)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (num_fac, nom, tel, dirc, pago, total_final, productos_json, "PENDIENTE", datetime.now().strftime("%d/%m/%Y %H:%M")))
                    for it in st.session_state.carrito:
                        c.execute("UPDATE productos_tienda SET stock = stock - ? WHERE id = ?", (it["cantidad"], it["id"]))
                    conn.commit()
                    conn.close()
                    
                    pdf = generar_factura_pdf(num_fac, nom, tel, dirc, st.session_state.carrito, total_final, estado="PENDIENTE")
                    st.balloons()
                    st.success(f"## ✅ ¡PEDIDO CONFIRMADO! Factura N° {num_fac}")
                    st.download_button("📄 DESCARGAR FACTURA PDF", data=pdf, file_name=f"CONTINENTAL_STYLE_{num_fac}.pdf", mime="application/pdf")
                    
                    msj = f"¡Hola! Pedido {NOMBRE_TIENDA} — {num_fac} ✅\n\n"
                    for it in st.session_state.carrito:
                        msj += f"✅ {it['nombre']} × {it['cantidad']} = RD$ {it['precio']*it['cantidad']:.0f}\n"
                    msj += f"\n💰 TOTAL: RD$ {total_final:,.0f}\n👤 {nom}\n📞 {tel}\n📍 {dirc}\n💳 {pago}"
                    link = f"https://wa.me/{TU_WHATSAPP.replace('+','')}?text={urllib.parse.quote(msj)}"
                    st.markdown(f"<a href='{link}' target='_blank' class='btn-whatsapp-grande'>📲 ENVIAR FACTURA POR WHATSAPP</a>", unsafe_allow_html=True)
                    
                    st.session_state.carrito = []
                    st.session_state.comprar = False
                    st.stop()
        return# 📦 CARGAR Y MOSTRAR PRODUCTOS
    conn = conectar()
    c = conn.cursor()
    sql = "SELECT id, nombre, categoria, descripcion, precio_costo, precio_venta, descuento, stock, tallas, foto, etiqueta FROM productos_tienda WHERE stock > 0"
    params = []
    if busqueda:
        sql += " AND (nombre LIKE ? OR descripcion LIKE ?)"
        params.extend([f"%{busqueda}%", f"%{busqueda}%"])
    if cat_limpia != "Todas":
        sql += " AND categoria LIKE ?"
        params.append(f"%{cat_limpia}%")
    if orden == "Precio: Menor → Mayor":
        sql += " ORDER BY precio_venta ASC"
    elif orden == "Precio: Mayor → Menor":
        sql += " ORDER BY precio_venta DESC"
    else:
        sql += " ORDER BY rowid DESC"
    c.execute(sql, params)
    productos = c.fetchall()
    conn.close()

    if not productos:
        st.info("📭 No hay productos con esos filtros")
    else:
        col1, col2, col3 = st.columns(3)
        cols = [col1, col2, col3]
        for i, p in enumerate(productos):
            idp, nom, cat, desc, pc, pv, dsc, stk, tal, fot, etiq = p
            precio_final = pv * (1 - dsc/100) if dsc else pv
            with cols[i % 3]:
                st.markdown("<div class='tarjeta-producto'>", unsafe_allow_html=True)
                
                # 🏷️ Etiqueta NUEVO / OFERTA
                if etiq == "NUEVO":
                    st.markdown("<span class='etiqueta-producto etiqueta-nuevo'>✨ NUEVO</span>", unsafe_allow_html=True)
                elif etiq == "OFERTA":
                    st.markdown("<span class='etiqueta-producto etiqueta-oferta'>🔥 OFERTA</span>", unsafe_allow_html=True)
                
                # 🖼️ Imagen
                if fot and os.path.exists(fot):
                    st.image(fot, use_container_width=True)
                else:
                    st.markdown("<div style='height:180px;display:flex;align-items:center;justify-content:center;background:#1e293b;border-radius:12px;color:#94a3b8'>🖼️ Sin imagen</div>", unsafe_allow_html=True)
                
                st.markdown(f"<h3 class='nombre-producto'>{nom}</h3>", unsafe_allow_html=True)
                st.caption(f"📂 {cat}")
                
                # 💰 Precio con descuento
                if dsc and dsc > 0:
                    st.markdown(f"<span class='precio-descuento'>RD$ {pv:,.0f}</span> <span class='precio'>RD$ {precio_final:,.0f}</span> <small>(-{dsc:.0f}%)</small>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span class='precio'>RD$ {precio_final:,.0f}</span>", unsafe_allow_html=True)
                
                st.markdown(f"<p class='info-dato'>📦 Disponible: {stk} unidades</p>", unsafe_allow_html=True)
                if tal:
                    st.markdown(f"<span class='etiqueta-tallas'>👟 {tal}</span>", unsafe_allow_html=True)
                if desc:
                    st.markdown(f"<p class='descripcion'>{desc}</p>", unsafe_allow_html=True)
                
                # ⚠️ Stock bajo
                if stk <= 5:
                    st.markdown(f"<div class='alerta-stock'>⚠️ ¡Solo quedan {stk} unidades!</div>", unsafe_allow_html=True)
                
                # 🛒 Agregar al carrito
                if st.button("🛒 Agregar", key=f"add_{idp}", type="primary", use_container_width=True):
                    agregar_al_carrito((idp, nom, precio_final, dsc, stk, fot, etiq))
                    st.rerun()
                
                st.markdown("</div>", unsafe_allow_html=True)

    # ℹ️ SOBRE NOSOTROS
    st.markdown("""
    <div class='seccion-nosotros'>
        <h3 class='nosotros-titulo'>🌍 Sobre CONTINENTAL STYLE</h3>
        <p class='nosotros-texto'>
            Somos tu puerta a la moda internacional. Traemos lo mejor de Europa y América directamente a ti. 
            Seleccionamos cuidadosamente cada pieza para ofrecerte calidad, estilo y elegancia incomparables.<br><br>
            ✅ Productos 100% originales<br>
            ✅ Atención personalizada<br>
            ✅ Envíos a toda la República Dominicana<br>
            ✅ Los mejores estilos del mundo, aquí mismo
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 📄 PIE DE PÁGINA CON REDES SOCIALES
    st.markdown(f"""
    <div class='footer-completo'>
        <div style='display:flex; flex-wrap:wrap; gap:30px;'>
            <div class='footer-columna' style='flex:2; min-width:200px;'>
                <h4>CONTINENTAL STYLE</h4>
                <p>{TAGLINE}</p>
                <p>📍 {TU_DIRECCION}</p>
                <p>⏰ {HORARIO}</p>
                <p>📞 {TU_TELEFONO}</p>
            </div>
            <div class='footer-columna' style='flex:1; min-width:150px;'>
                <h4>Enlaces Rápidos</h4>
                <p>🏪 Tienda</p>
                <p>👟 Calzado</p>
                <p>👕 Ropa</p>
                <p>💎 Accesorios</p>
            </div>
            <div class='footer-columna' style='flex:1; min-width:150px;'>
                <h4>Síguenos</h4>
                <p>📸 <a href='https://instagram.com/continentalstyle.do' target='_blank' style='color:#94a3b8; text-decoration:none;'>Instagram</a></p>
                <p>📘 <a href='https://facebook.com/continentalstyle.do' target='_blank' style='color:#94a3b8; text-decoration:none;'>Facebook</a></p>
                <p>🎵 <a href='https://tiktok.com/@continentalstyle.do' target='_blank' style='color:#94a3b8; text-decoration:none;'>TikTok</a></p>
            </div>
            <div class='footer-columna' style='flex:2; min-width:200px;'>
                <h4>Métodos de Pago</h4>
                <div class='footer-pagos'>
                    <span class='pago-icono'>💵 Efectivo</span>
                    <span class='pago-icono'>🏦 Transferencia</span>
                    <span class='pago-icono'>📱 Pago Móvil</span>
                    <span class='pago-icono'>💳 Tarjeta</span>
                </div>
            </div>
        </div>
        <div style='text-align:center; margin-top:30px; padding-top:20px; border-top:1px solid #1e293b; color:#64748b; font-size:13px;'>
            © 2026 CONTINENTAL STYLE — Todos los derechos reservados · Diseñado con 🌍 en Rep. Dominicana
        </div>
    </div>
    """, unsafe_allow_html=True)

# ==================================================
# 🔐 INICIO DE SESIÓN — ADMINISTRADOR
# ==================================================
def pagina_login():
    st.markdown(LOGO_HTML, unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["🔑 Iniciar Sesión", "✍️ Solicitar Acceso"])
    
    with t1:
        cor = st.text_input("Correo Electrónico")
        cla = st.text_input("Contraseña", type="password")
        if st.button("🔑 Entrar", type="primary", use_container_width=True):
            conn = conectar()
            c = conn.cursor()
            c.execute("SELECT id_usuario, correo, contraseña, nombre, es_admin, estado FROM usuarios WHERE correo = ?", (cor,))
            u = c.fetchone()
            conn.close()
            if u and u[2] == cifrar_contraseña(cla):
                if u[5] == "bloqueado":
                    st.error("🚫 Cuenta bloqueada")
                elif u[5] == "pendiente":
                    st.warning("⏳ Cuenta pendiente de aprobación")
                elif u[5] == "aprobado":
                    st.session_state.usuario = {"id":u[0],"correo":u[1],"nombre":u[3]}
                    st.session_state.es_admin = bool(u[4])
                    st.session_state.panel_admin = True
                    st.success(f"✅ ¡Bienvenido, {u[3]}!")
                    st.rerun()
            else:
                st.error("❌ Correo o contraseña incorrectos")
    
    with t2:
        nom = st.text_input("Tu Nombre Completo")
        cor_reg = st.text_input("Tu Correo Electrónico")
        cla1 = st.text_input("Contraseña", type="password")
        cla2 = st.text_input("Repetir Contraseña", type="password")
        if st.button("✍️ Enviar Solicitud", type="primary", use_container_width=True):
            if cla1 != cla2:
                st.error("❌ Las contraseñas no coinciden")
            elif len(cla1) < 6:
                st.error("⚠️ Mínimo 6 caracteres")
            else:
                conn = conectar()
                c = conn.cursor()
                try:
                    c.execute("INSERT INTO usuarios VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (generar_id_usuario(), cor_reg, cifrar_contraseña(cla1), nom, "pendiente", 0, datetime.now().strftime("%d/%m/%Y %H:%M")))
                    conn.commit()
                    st.success("✅ ¡Solicitud enviada! Espera aprobación del administrador")
                except:
                    st.error("⚠️ Este correo ya está registrado")
                conn.close()

# ==================================================
# ⚙️ PANEL DE ADMINISTRACIÓN — SOLO TÚ 🔒
# ==================================================
def panel_administrador():
    st.markdown(LOGO_HTML, unsafe_allow_html=True)
    st.markdown("<hr>", unsafe_allow_html=True)

    # 🔝 MENÚ HORIZONTAL
    menu_sup = ["📊 Dashboard", "🏪 Productos", "➕ Agregar", "📦 Pedidos", "💰 Abonos", "👥 Usuarios"]
    sel = st.radio("", menu_sup, horizontal=True, label_visibility="collapsed")
    st.markdown("<hr>", unsafe_allow_html=True)

    # 📊 DASHBOARD
    if sel == "📊 Dashboard":
        s = calcular_estadisticas()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"<div class='tarjeta-dato'><div class='numero-grande'>{s['productos']}</div><div class='info-dato'>📦 Productos</div></div>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<div class='tarjeta-dato'><div class='numero-grande'>RD$ {s['inversion']:,.0f}</div><div class='info-dato'>💰 Inversión</div></div>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<div class='tarjeta-dato'><div class='numero-grande'>RD$ {s['valor']:,.0f}</div><div class='info-dato'>🏷️ Valor Tienda</div></div>", unsafe_allow_html=True)
        c4, c5, c6 = st.columns(3)
        with c4:
            st.markdown(f"<div class='tarjeta-dato'><div class='numero-grande' style='color:#10b981'>RD$ {s['ganancia']:,.0f}</div><div class='info-dato'>💵 Ganancia</div></div>", unsafe_allow_html=True)
        with c5:
            st.markdown(f"<div class='tarjeta-dato'><div class='numero-grande' style='color:#10b981'>{s['porcentaje']:.1f}%</div><div class='info-dato'>📈 % Ganancia</div></div>", unsafe_allow_html=True)
        with c6:
            st.markdown(f"<div class='tarjeta-dato'><div class='numero-grande'>{s['pendientes']}</div><div class='info-dato'>📋 Pedidos Pendientes</div></div>", unsafe_allow_html=True)
        
        st.markdown("<hr>", unsafe_allow_html=True)
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT nombre, stock FROM productos_tienda WHERE stock <= 5 AND stock > 0 ORDER BY stock ASC")
        bajo = c.fetchall()
        conn.close()
        if bajo:
            st.warning("⚠️ STOCK BAJO:")
            for n, c in bajo:
                st.markdown(f"- **{n}**: {c} unidades")

    # 🏪 PRODUCTOS — EDITAR / ELIMINAR
    elif sel == "🏪 Productos":
        st.subheader("📋 Lista de Productos")
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT id, nombre, categoria, precio_costo, precio_venta, descuento, stock, tallas, descripcion, foto, etiqueta FROM productos_tienda ORDER BY nombre")
        prod = c.fetchall()
        conn.close()
        if not prod:
            st.info("📭 Sin productos registrados")
        else:
            sel_prod = st.selectbox("Selecciona para editar:", ["---"] + [f"{p[0]} - {p[1]}" for p in prod])
            if sel_prod != "---":
                idp = int(sel_prod.split(" - ")[0])
                p = next(x for x in prod if x[0]==idp)
                with st.expander("✏️ Editar / Eliminar", expanded=True):
                    with st.form("editar_prod"):
                        nom = st.text_input("Nombre", value=p[1])
                        cat = st.selectbox("Categoría", ["Calzado", "Ropa Hombre", "Ropa Mujer", "Niños", "Accesorios", "Perfumes / Colonias"], index=["Calzado", "Ropa Hombre", "Ropa Mujer", "Niños", "Accesorios", "Perfumes / Colonias"].index(p[2]))
                        desc = st.text_area("Descripción", value=p[3] or "")
                        c1,c2 = st.columns(2)
                        with c1: pc = st.number_input("💰 Costo", min_value=0.0, step=10.0, value=p[4])
                        with c2: pv = st.number_input("💵 Venta", min_value=0.0, step=10.0, value=p[5])
                        c3,c4 = st.columns(2)
                        with c3: dsc = st.number_input("🔥 Descuento %", 0.0, 100.0, 5.0, value=p[6])
                        with c4: stk = st.number_input("📦 Cantidad", 0, step=1, value=p[7])
                        tal = st.text_input("Tallas", value=p[8] or "")
                        etiq = st.selectbox("🏷️ Etiqueta Especial", ["Ninguna", "NUEVO", "OFERTA"], index=["Ninguna", "NUEVO", "OFERTA"].index(p[10] or "Ninguna"))
                        foto_nueva = st.file_uploader("📷 Nueva Imagen", type=["jpg","jpeg","png"])
                        g1,g2 = st.columns(2)
                        with g1: guardar = st.form_submit_button("💾 Guardar Cambios", type="primary")
                        with g2: eliminar = st.form_submit_button("🗑️ Eliminar")
                        
                        if guardar:
                            ruta_foto = p[9]
                            if foto_nueva:
                                if ruta_foto and os.path.exists(ruta_foto): os.remove(ruta_foto)
                                if not os.path.exists("fotos_productos"): os.makedirs("fotos_productos")
                                ruta_foto = f"fotos_productos/{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto_nueva.name}"
                                with open(ruta_foto, "wb") as f: f.write(foto_nueva.getbuffer())
                            conn = conectar()
                            c = conn.cursor()
                            c.execute("UPDATE productos_tienda SET nombre=?, categoria=?, descripcion=?, precio_costo=?, precio_venta=?, descuento=?, stock=?, tallas=?, foto=?, etiqueta=? WHERE id=?",
                                      (nom, cat, desc, pc, pv, dsc, stk, tal, ruta_foto, etiq if etiq!="Ninguna" else None, idp))
                            conn.commit()
                            conn.close()
                            st.success("✅ Producto actualizado")
                            st.rerun()
                        if eliminar:
                            if p[9] and os.path.exists(p[9]): os.remove(p[9])
                            conn = conectar()
                            c = conn.cursor()
                            c.execute("DELETE FROM productos_tienda WHERE id=?", (idp,))
                            conn.commit()
                            conn.close()
                            st.warning("🗑️ Producto eliminado")
                            st.rerun()# ➕ AGREGAR PRODUCTO NUEVO
    elif sel == "➕ Agregar":
        st.subheader("➕ Agregar Nuevo Producto")
        with st.form("agregar_producto", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                nombre = st.text_input("Nombre del Producto *")
                categoria = st.selectbox("Categoría *", ["Calzado", "Ropa Hombre", "Ropa Mujer", "Niños", "Accesorios", "Perfumes / Colonias"])
            with c2:
                precio_costo = st.number_input("💰 Precio de Costo *", min_value=0.0, step=10.0)
                precio_venta = st.number_input("💵 Precio de Venta *", min_value=0.0, step=10.0)
            
            c3, c4 = st.columns(2)
            with c3:
                descuento = st.slider("🔥 Descuento (%)", 0, 50, 0)
                stock = st.number_input("📦 Cantidad / Stock *", min_value=0, step=1)
            with c4:
                tallas = st.text_input("Tallas disponibles (ej: 38,39,40,41)")
                etiqueta = st.selectbox("🏷️ Etiqueta Especial", ["Ninguna", "NUEVO", "OFERTA"])
            
            descripcion = st.text_area("Descripción / Características")
            foto = st.file_uploader("📷 Imagen del Producto", type=["jpg", "jpeg", "png"])
            
            guardar = st.form_submit_button("✅ GUARDAR PRODUCTO", type="primary", use_container_width=True)
            
            if guardar:
                if not nombre or not precio_costo or not precio_venta or stock <= 0:
                    st.error("⚠️ Completa los campos obligatorios (*)")
                else:
                    ruta_foto = None
                    if foto:
                        if not os.path.exists("fotos_productos"):
                            os.makedirs("fotos_productos")
                        ruta_foto = f"fotos_productos/{datetime.now().strftime('%Y%m%d%H%M%S')}_{foto.name}"
                        with open(ruta_foto, "wb") as f:
                            f.write(foto.getbuffer())
                    
                    conn = conectar()
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO productos_tienda
                        (nombre, categoria, descripcion, precio_costo, precio_venta, descuento, stock, tallas, foto, etiqueta)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        nombre, categoria, descripcion, precio_costo, precio_venta,
                        descuento, stock, tallas, ruta_foto, etiqueta if etiqueta != "Ninguna" else None
                    ))
                    conn.commit()
                    conn.close()
                    
                    st.success(f"✅ Producto **{nombre}** agregado correctamente!")
                    st.balloons()

    # 📦 GESTIÓN DE PEDIDOS
    elif sel == "📦 Pedidos":
        st.subheader("📦 Lista de Pedidos")
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT id_pedido, numero_factura, nombre_cliente, telefono, total, estado, fecha_pedido FROM pedidos ORDER BY fecha_pedido DESC")
        pedidos = c.fetchall()
        conn.close()
        
        if not pedidos:
            st.info("📭 No hay pedidos registrados")
        else:
            filtro_estado = st.multiselect("Filtrar por estado:", ["PENDIENTE", "ABONANDO", "PAGADO", "ENVIADO", "CANCELADO"], default=["PENDIENTE", "ABONANDO"])
            for p in pedidos:
                if p[5] not in filtro_estado:
                    continue
                with st.expander(f"📄 {p[1]} — {p[2]} — RD$ {p[4]:,.0f} — {p[5]}"):
                    st.write(f"📞 Teléfono: {p[3]}")
                    st.write(f"📅 Fecha: {p[6]}")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        nuevo_estado = st.selectbox("Cambiar Estado:", 
                            ["PENDIENTE", "ABONANDO", "PAGADO", "ENVIADO", "CANCELADO"],
                            index=["PENDIENTE", "ABONANDO", "PAGADO", "ENVIADO", "CANCELADO"].index(p[5]),
                            key=f"est_{p[0]}")
                    with c2:
                        if st.button("✅ Actualizar", key=f"act_{p[0]}"):
                            conn = conectar()
                            c = conn.cursor()
                            c.execute("UPDATE pedidos SET estado = ? WHERE id_pedido = ?", (nuevo_estado, p[0]))
                            conn.commit()
                            conn.close()
                            st.success("✅ Estado actualizado")
                            st.rerun()
                    
                    if st.button("📄 Generar Factura PDF", key=f"pdf_{p[0]}"):
                        conn = conectar()
                        c = conn.cursor()
                        c.execute("SELECT numero_factura, nombre_cliente, telefono, direccion, metodo_pago, total, productos, estado FROM pedidos WHERE id_pedido = ?", (p[0],))
                        fact = c.fetchone()
                        c.execute("SELECT descripcion, valor, fecha FROM abonos WHERE numero_factura = ?", (fact[0],))
                        abonos = c.fetchall()
                        conn.close()
                        
                        productos = eval(fact[6]) if fact[6] else []
                        lista_abonos = [{"descripcion":a[0], "valor":a[1], "fecha":a[2]} for a in abonos]
                        pdf = generar_factura_pdf(fact[0], fact[1], fact[2], fact[3], productos, fact[5], lista_abonos, fact[7])
                        st.download_button("📄 Descargar Factura", data=pdf, file_name=f"FACTURA_{fact[0]}.pdf", mime="application/pdf")

    # 💰 GESTIÓN DE ABONOS
    elif sel == "💰 Abonos":
        st.subheader("💰 Control de Abonos")
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT numero_factura, nombre_cliente, total, estado FROM pedidos WHERE estado IN ('PENDIENTE', 'ABONANDO') ORDER BY fecha_pedido DESC")
        pedidos = c.fetchall()
        conn.close()
        
        if not pedidos:
            st.info("📭 No hay pedidos pendientes para abonos")
        else:
            fac_sel = st.selectbox("Selecciona Factura:", [f"{p[0]} — {p[1]} — Total: RD$ {p[2]:,.0f}" for p in pedidos])
            num_fac = fac_sel.split(" — ")[0]
            total = float(fac_sel.split("RD$ ")[1].replace(",", ""))
            
            conn = conectar()
            c = conn.cursor()
            c.execute("SELECT descripcion, valor, fecha FROM abonos WHERE numero_factura = ?", (num_fac,))
            abonos = c.fetchall()
            conn.close()
            
            total_abonado = sum(a[1] for a in abonos)
            saldo = total - total_abonado
            
            c1, c2, c3 = st.columns(3)
            c1.metric("💰 Total Factura", f"RD$ {total:,.0f}")
            c2.metric("✅ Total Abonado", f"RD$ {total_abonado:,.0f}")
            c3.metric("🔴 Saldo Pendiente", f"RD$ {saldo:,.0f}")
            
            st.markdown("---")
            st.subheader("➕ Registrar Nuevo Abono")
            with st.form("nuevo_abono"):
                desc = st.text_input("Descripción / Concepto")
                valor = st.number_input("Monto del Abono RD$", min_value=0.0, step=50.0)
                if st.form_submit_button("💳 Registrar Abono", type="primary"):
                    if valor <= 0:
                        st.error("⚠️ El monto debe ser mayor a 0")
                    else:
                        conn = conectar()
                        c = conn.cursor()
                        c.execute("INSERT INTO abonos VALUES (?, ?, ?, ?, ?)",
                                  (None, num_fac, desc, valor, datetime.now().strftime("%d/%m/%Y %H:%M")))
                        nuevo_saldo = saldo - valor
                        nuevo_estado = "PAGADO" if nuevo_saldo <= 0 else "ABONANDO"
                        c.execute("UPDATE pedidos SET estado = ? WHERE numero_factura = ?", (nuevo_estado, num_fac))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Abono registrado! Saldo pendiente: RD$ {max(0, nuevo_saldo):,.0f}")
                        st.rerun()
            
            if abonos:
                st.markdown("---")
                st.subheader("📋 Historial de Abonos")
                for i, a in enumerate(abonos, 1):
                    st.write(f"{i}. **{a[0]}** — RD$ {a[1]:,.0f} — {a[2]}")

    # 👥 GESTIÓN DE USUARIOS
    elif sel == "👥 Usuarios":
        st.subheader("👥 Gestión de Usuarios")
        conn = conectar()
        c = conn.cursor()
        c.execute("SELECT id_usuario, correo, nombre, estado, es_admin, fecha_registro FROM usuarios ORDER BY fecha_registro DESC")
        usuarios = c.fetchall()
        conn.close()
        
        for u in usuarios:
            estado_badge = {
                "pendiente": "badge-pendiente",
                "aprobado": "badge-pagado",
                "bloqueado": "badge-admin"
            }.get(u[3], "")
            st.markdown(f"""
            <div style='padding:15px; border-radius:12px; background:#1e293b; margin:8px 0; display:flex; justify-content:space-between; align-items:center;'>
                <div>
                    <strong>{u[2]}</strong> — {u[1]}<br>
                    <small>ID: {u[0]} | {u[5]}</small>
                </div>
                <span class='{estado_badge}'>{u[3].upper()}</span>
            </div>
            """, unsafe_allow_html=True)
            
            if not u[4]:
                c1, c2, c3 = st.columns(3)
                with c1:
                    if u[3] == "pendiente" and st.button("✅ Aprobar", key=f"apr_{u[0]}"):
                        conn = conectar()
                        c = conn.cursor()
                        c.execute("UPDATE usuarios SET estado = 'aprobado' WHERE id_usuario = ?", (u[0],))
                        conn.commit()
                        conn.close()
                        st.success("✅ Usuario aprobado")
                        st.rerun()
                with c2:
                    if u[3] != "bloqueado" and st.button("🚫 Bloquear", key=f"blo_{u[0]}"):
                        conn = conectar()
                        c = conn.cursor()
                        c.execute("UPDATE usuarios SET estado = 'bloqueado' WHERE id_usuario = ?", (u[0],))
                        conn.commit()
                        conn.close()
                        st.warning("🚫 Usuario bloqueado")
                        st.rerun()
                with c3:
                    if u[3] == "bloqueado" and st.button("🔓 Desbloquear", key=f"des_{u[0]}"):
                        conn = conectar()
                        c = conn.cursor()
                        c.execute("UPDATE usuarios SET estado = 'aprobado' WHERE id_usuario = ?", (u[0],))
                        conn.commit()
                        conn.close()
                        st.success("🔓 Usuario desbloqueado")
                        st.rerun()

    # 🔒 CAMBIAR CONTRASEÑA ADMIN + VER TIENDA + CERRAR SESIÓN ✅
    st.sidebar.markdown("---")
    
    # 🏪 BOTÓN: VOLVER A LA TIENDA
    if st.sidebar.button("🏪 Ver Tienda", use_container_width=True, type="primary"):
        st.session_state.panel_admin = False
        st.rerun()
    
    # 🔒 CAMBIAR CONTRASEÑA
    if st.sidebar.button("🔒 Cambiar Contraseña Admin", use_container_width=True):
        st.session_state.cambiar_clave = True
        st.rerun()
    
    # 🚪 CERRAR SESIÓN
    st.sidebar.markdown("---")
    if st.sidebar.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state.usuario = None
        st.session_state.es_admin = False
        st.session_state.panel_admin = False
        st.rerun()
    
    if st.session_state.get("cambiar_clave"):
        st.subheader("🔒 Cambiar Contraseña")
        with st.form("cambiar_contraseña"):
            clave_actual = st.text_input("Contraseña Actual", type="password")
            clave_nueva = st.text_input("Nueva Contraseña", type="password")
            clave_conf = st.text_input("Repetir Nueva Contraseña", type="password")
            if st.form_submit_button("✅ Actualizar"):
                if clave_nueva != clave_conf:
                    st.error("❌ Las contraseñas no coinciden")
                elif len(clave_nueva) < 6:
                    st.error("⚠️ Mínimo 6 caracteres")
                else:
                    conn = conectar()
                    c = conn.cursor()
                    c.execute("SELECT contraseña FROM usuarios WHERE es_admin = 1")
                    actual = c.fetchone()[0]
                    if actual == cifrar_contraseña(clave_actual):
                        c.execute("UPDATE usuarios SET contraseña = ? WHERE es_admin = 1", (cifrar_contraseña(clave_nueva),))
                        conn.commit()
                        st.success("✅ Contraseña actualizada correctamente")
                    else:
                        st.error("❌ Contraseña actual incorrecta")
                    conn.close()
                st.session_state.cambiar_clave = False
        if st.button("❌ Cancelar"):
            st.session_state.cambiar_clave = False
            st.rerun()

# ==================================================
# 🚀 CONTROLADOR PRINCIPAL — TODO JUNTO
# ==================================================
def main():
    # 📄 PÁGINA DE LOGIN
    if st.session_state.get("mostrar_login") and not st.session_state.usuario:
        pagina_login()
        if st.button("← Volver a la Tienda", use_container_width=True):
            st.session_state.mostrar_login = False
            st.rerun()
        return
    
    # ⚙️ PANEL DE ADMINISTRACIÓN
    if st.session_state.get("panel_admin") and st.session_state.es_admin:
        panel_administrador()
        return
    
    # 🏪 TIENDA PÚBLICA (por defecto)
    pagina_tienda_publica()

# ==================================================
# 🏁 EJECUTAR — ¡LISTO!
# ==================================================
if __name__ == "__main__":
    main()