#!/usr/bin/env python3
import os
import json
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, send_from_directory, abort)
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user, UserMixin)

# ─────── Configuración básica ───────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cámbiala_por_una_clave_segura")

# LoginManager
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

# Directorio raíz del proyecto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Directorio donde guardamos los JSON de configuración
CONFIG_DIR = os.path.join(BASE_DIR, "configs")
os.makedirs(CONFIG_DIR, exist_ok=True)  # Lo creamos si no existe

# Carpeta de logs para el Filebrowser
BASE_PATH = os.environ.get("GAMEHUB_BASE", BASE_DIR)

# ─────── Usuario de ejemplo (flask-login) ───────
class User(UserMixin):
    def __init__(self, id):
        self.id = id

# Aquí cargarías usuarios reales desde DB
@login_manager.user_loader
def load_user(user_id):
    return User(user_id)

# ─────── FILTROS JINJA ───────
from datetime import datetime
@app.template_filter("datetimeformat")
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime("%d.%m.%Y %H:%M")

# ─────── RUTAS DE AUTENTICACIÓN ───────
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        # TODO: Valida credenciales REALMENTE
        if u == "david" and p == "a":
            user = User(u)
            login_user(user)
            return redirect(url_for("index"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ─────── RUTA PRINCIPAL ───────
@app.route("/")
@login_required
def index():
    # Carga tu data de /data/servers.json
    servers_file = os.path.join(BASE_DIR, "data", "servers.json")
    with open(servers_file, "r") as f:
        servers = json.load(f)
    return render_template("index.html", servers=servers)

# … aquí van tus rutas crear_ark, crear_minecraft, crear_zomboid, editar_*, filebrowser, etc. …

# ─────── RUTAS DE CONFIGURACIÓN TIPO NITRADO ───────

def get_config_path(instancia):
    """Ruta del JSON de configuración para cada instancia."""
    return os.path.join(CONFIG_DIR, f"{instancia}.json")

def load_server_config(instancia):
    """Carga configuración desde JSON; devuelve valores por defecto si no existe."""
    path = get_config_path(instancia)
    if not os.path.isfile(path):
        return {
            "server_name": instancia,
            "server_password": "",
            "admin_password": "",
            "map_name": "The Island",
            "enable_3rd_person": False,
            "enable_crosshair": False,
            "disable_pvp": False,
            "enable_hardcore": False,
            "enable_join_msg": True,
            "enable_leave_msg": False
        }
    with open(path, "r") as f:
        return json.load(f)

def save_server_config(instancia, data):
    """Guarda el diccionario `data` en el JSON correspondiente."""
    path = get_config_path(instancia)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/config/<instancia>/", methods=["GET", "POST"])
@login_required
def server_config(instancia):
    """
    GET: Muestra formulario con valores actuales.
    POST: Recibe cambios y los guarda.
    """
    cfg = load_server_config(instancia)

    if request.method == "POST":
        # Actualiza los campos según el formulario
        cfg["server_name"]       = request.form.get("server_name", cfg["server_name"])
        cfg["server_password"]   = request.form.get("server_password", "")
        cfg["admin_password"]    = request.form.get("admin_password", "")
        cfg["map_name"]          = request.form.get("map_name", cfg["map_name"])
        cfg["enable_3rd_person"] = bool(request.form.get("enable_3rd_person"))
        cfg["enable_crosshair"]  = bool(request.form.get("enable_crosshair"))
        cfg["disable_pvp"]       = bool(request.form.get("disable_pvp"))
        cfg["enable_hardcore"]   = bool(request.form.get("enable_hardcore"))
        cfg["enable_join_msg"]   = bool(request.form.get("enable_join_msg"))
        cfg["enable_leave_msg"]  = bool(request.form.get("enable_leave_msg"))
        save_server_config(instancia, cfg)
        flash("⚙️ Configuración guardada correctamente.", "success")
        return redirect(url_for("server_config", instancia=instancia))

    # Mapas preinstalados (puedes ampliarlos o leer dinámicamente)
    mapas_pre = ["The Island", "The Lost World", "Apako Islands", "IceAge"]
    return render_template("server_config.html",
                           instancia=instancia,
                           cfg=cfg,
                           mapas_pre=mapas_pre)

@app.route("/config/<instancia>/delete", methods=["GET"])
@login_required
def delete_config(instancia):
    """
    Elimina el fichero JSON de configuración de la instancia.
    """
    path = get_config_path(instancia)
    if os.path.isfile(path):
        os.remove(path)
        flash("🗑️ Configuración eliminada.", "info")
    else:
        flash("⚠️ No existe configuración para eliminar.", "error")
    return redirect(url_for("index"))

# ─────── PUNTO DE ENTRADA ───────
if __name__ == "__main__":
    # Imprime rutas (útil para depurar)
    print("\n––––––––– Rutas registradas –––––––––")
    print(app.url_map)
    print("––––––––––––––––––––––––––––––––––––\n")
    app.run(host="0.0.0.0", port=5002, debug=True)
