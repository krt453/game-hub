import os
import json
import shutil
import subprocess
from flask import (
    Flask, render_template, request,
    redirect, url_for, flash
)
from jinja2 import Template
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)

app = Flask(__name__)

# ——— Configuración de sesión y Flask-Login ———
app.secret_key = os.environ.get("SECRET_KEY", "cámbiala_por_una_frase_secreta_y_larga")

login_manager = LoginManager(app)
login_manager.login_view = "login"

# Usuario único "admin" en memoria
USERS = {
    "david": {
        "password": "a"  # ← ¡Cámbiala aquí!
    }
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        if u in USERS and p == USERS[u]["password"]:
            user = User(u)
            login_user(user)
            return redirect(request.args.get("next") or url_for("index"))
        else:
            flash("Usuario o contraseña incorrectos", "error")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.before_request
def proteger_rutas():
    # Permitir sin login: endpoints 'login' y 'static'
    if request.endpoint in ("login", "static"):
        return
    if not current_user.is_authenticated:
        return redirect(url_for("login", next=request.path))

# ——— RUTAS DE GESTIÓN DE SERVIDORES ———

# Rutas y constantes fijas
BASE_PATH   = "/opt/servidorcasa/compose"
STATE_FILE  = os.path.join(BASE_PATH, "gamehub-app/data/servers.json")
TEMPLATES   = os.path.join(BASE_PATH, "gamehub-app/templates_config")
INITIAL_STATE = {"ark": [], "minecraft": [], "zomboid": []}

def init_state_file():
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(INITIAL_STATE, f, indent=4)
    return INITIAL_STATE.copy()

def cargar_estado():
    if not os.path.exists(STATE_FILE):
        return init_state_file()
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except (json.JSONDecodeError, ValueError):
        return init_state_file()
    # Migración mínima: convertir strings sueltos a dicts
    for juego in ("ark", "minecraft", "zomboid"):
        nueva = []
        for entry in data.get(juego, []):
            if isinstance(entry, str):
                nueva.append({"nombre": entry, "estado": "parado"})
            else:
                nueva.append(entry)
        data[juego] = nueva
    return data

def guardar_estado(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f, indent=4)

def ejecutar_compose(path, cmd="up -d"):
    subprocess.Popen(f"docker compose {cmd}", cwd=path, shell=True)

# — Índice / listado —
@app.route("/")
@login_required
def index():
    servers = cargar_estado()
    return render_template("index.html", servers=servers)

# —— ARK ——
@app.route("/nuevo_ark")
@login_required
def nuevo_ark():
    # Lee mapas disponibles desde plantilla
    mapas = ["TheIsland","ScorchedEarth_P","Aberration_P","Ragnarok","Extinction","Valguero_P","Genesis","Genesis2","CrystalIsles","LostIsland","Fjordur"]
    return render_template("crear_ark.html", mapas=mapas)

@app.route("/crear_ark", methods=["POST"])
@login_required
def crear_ark():
    form    = request.form
    data    = cargar_estado()
    nombre  = f"srv-ark-{len(data['ark'])+1}"
    puerto  = int(form["puerto"])
    srv = {
        "nombre": nombre,
        "mapa": form["mapa"],
        "mods": form["mods"],
        "cluster": form["cluster"],
        "puerto": puerto,
        "estado": "activo"
    }
    data["ark"].append(srv)
    guardar_estado(data)

    # Renderizar docker-compose.yml desde plantilla
    dst = os.path.join(BASE_PATH, nombre)
    os.makedirs(dst, exist_ok=True)
    tpl = os.path.join(TEMPLATES, "ark", "docker-compose.yml")
    raw = open(tpl).read()
    ports = {
        "port_game": puerto,
        "port_query": puerto + 1,
        "port_rcon": puerto + 2
    }
    rendered = Template(raw).render(
        nombre_servidor=nombre,
        mapa=srv["mapa"],
        mods=srv["mods"],
        cluster=srv["cluster"],
        **ports
    )
    open(os.path.join(dst, "docker-compose.yml"), "w").write(rendered)
    ejecutar_compose(dst, "up -d")
    return redirect(url_for("index"))

# —— Minecraft ——
@app.route("/nuevo_minecraft")
@login_required
def nuevo_minecraft():
    versiones = ["vanilla","paper","spigot","forge"]
    return render_template("crear_minecraft.html", versiones=versiones)

@app.route("/crear_minecraft", methods=["POST"])
@login_required
def crear_minecraft():
    form   = request.form
    data   = cargar_estado()
    nombre = f"srv-mc-{len(data['minecraft'])+1}"
    puerto = int(form["puerto"])
    srv = {
        "nombre": nombre,
        "version": form["version"],
        "memory": form["memory"],
        "rcon_pass": form["rcon_pass"],
        "descripcion": form["descripcion"],
        "mundo": form["mundo"],
        "ops": form["ops"],
        "puerto": puerto,
        "estado": "activo"
    }
    data["minecraft"].append(srv)
    guardar_estado(data)

    dst = os.path.join(BASE_PATH, nombre)
    os.makedirs(dst, exist_ok=True)
    tpl = os.path.join(TEMPLATES, "minecraft", "docker-compose.yml")
    raw = open(tpl).read()
    ports = {"port_game": puerto, "port_rcon": puerto+1}
    rendered = Template(raw).render(
        nombre_servidor=nombre,
        version=srv["version"],
        memory=srv["memory"],
        rcon_pass=srv["rcon_pass"],
        descripcion=srv["descripcion"],
        mundo=srv["mundo"],
        ops=srv["ops"],
        **ports
    )
    open(os.path.join(dst, "docker-compose.yml"), "w").write(rendered)
    ejecutar_compose(dst, "up -d")
    return redirect(url_for("index"))

# —— Zomboid ——
@app.route("/nuevo_zomboid")
@login_required
def nuevo_zomboid():
    mapas = ["TheIsland","ScorchedEarth_P","Aberration_P","Ragnarok","Extinction","Valguero_P"]
    return render_template("crear_zomboid.html", mapas=mapas)

@app.route("/crear_zomboid", methods=["POST"])
@login_required
def crear_zomboid():
    form = request.form
    data = cargar_estado()
    nombre = f"srv-zomboid-{len(data['zomboid'])+1}"
    puerto = int(form["puerto"])
    srv = {
        "nombre": nombre,
        "mapa": form["mapa"],
        "mods": form["mods"],
        "password": form["password"],
        "public": form["public"],
        "max_players": form["max_players"],
        "puerto": puerto,
        "estado": "activo"
    }
    data["zomboid"].append(srv)
    guardar_estado(data)

    # Clona la plantilla oficial de Zomboid (o tu propia plantilla)
    dst = os.path.join(BASE_PATH, nombre)
    subprocess.run(f"git clone https://github.com/Danixu/project-zomboid-server-docker.git {nombre}", cwd=BASE_PATH, shell=True)
    # Copia .env.template a .env y ajusta valores
    envf = os.path.join(dst, ".env")
    shutil.copyfile(os.path.join(dst, ".env.template"), envf)
    lines = []
    for line in open(envf):
        if line.startswith("PZ_MAP="):
            lines.append(f'PZ_MAP="{srv["mapa"]}"\n')
        elif line.startswith("PZ_MODS="):
            lines.append(f'PZ_MODS="{srv["mods"]}"\n')
        elif line.startswith("PZ_PASSWORD="):
            lines.append(f'PZ_PASSWORD="{srv["password"]}"\n')
        elif line.startswith("PZ_PUBLIC="):
            lines.append(f'PZ_PUBLIC={srv["public"]}\n')
        elif line.startswith("PZ_MAX_PLAYERS="):
            lines.append(f'PZ_MAX_PLAYERS={srv["max_players"]}\n')
        elif line.startswith("PZ_SERVER_PORT="):
            lines.append(f'PZ_SERVER_PORT={srv["puerto"]}\n')
        else:
            lines.append(line)
    open(envf, "w").writelines(lines)
    ejecutar_compose(dst, "up -d")
    return redirect(url_for("index"))

# —— Editar ARK ——
@app.route("/editar/ark/<instancia>")
@login_required
def editar_ark_form(instancia):
    data = cargar_estado()
    srv = next((s for s in data["ark"] if s["nombre"]==instancia), None)
    if not srv:
        return redirect(url_for("index"))
    mapas = ["TheIsland","ScorchedEarth_P","Aberration_P","Ragnarok","Extinction","Valguero_P","Genesis","Genesis2","CrystalIsles","LostIsland","Fjordur"]
    return render_template("editar_ark.html", srv=srv, mapas=mapas)

@app.route("/editar/ark/<instancia>", methods=["POST"])
@login_required
def editar_ark(instancia):
    form = request.form
    data = cargar_estado()
    for s in data["ark"]:
        if s["nombre"] == instancia:
            s["mapa"]    = form["mapa"]
            s["mods"]    = form["mods"]
            s["cluster"] = form["cluster"]
            s["puerto"]  = int(form["puerto"])
            break
    guardar_estado(data)

    dst = os.path.join(BASE_PATH, instancia)
    tpl = os.path.join(TEMPLATES, "ark", "docker-compose.yml")
    raw = open(tpl).read()
    ports = {
        "port_game": s["puerto"],
        "port_query": s["puerto"]+1,
        "port_rcon": s["puerto"]+2
    }
    rendered = Template(raw).render(
        nombre_servidor=instancia,
        mapa=s["mapa"], mods=s["mods"], cluster=s["cluster"], **ports
    )
    open(os.path.join(dst, "docker-compose.yml"), "w").write(rendered)
    subprocess.run(f"docker compose -f docker-compose.yml down", cwd=dst, shell=True)
    ejecutar_compose(dst, "up -d")
    return redirect(url_for("index"))

# —— Editar Minecraft ——
@app.route("/editar/minecraft/<instancia>")
@login_required
def editar_mc_form(instancia):
    data = cargar_estado()
    srv = next((s for s in data["minecraft"] if s["nombre"]==instancia), None)
    if not srv:
        return redirect(url_for("index"))
    versiones = ["vanilla","paper","spigot","forge"]
    return render_template("editar_minecraft.html", srv=srv, versiones=versiones)

@app.route("/editar/minecraft/<instancia>", methods=["POST"])
@login_required
def editar_mc(instancia):
    form = request.form
    data = cargar_estado()
    for s in data["minecraft"]:
        if s["nombre"] == instancia:
            s["version"]    = form["version"]
            s["memory"]     = form["memory"]
            s["rcon_pass"]  = form["rcon_pass"]
            s["descripcion"]= form["descripcion"]
            s["mundo"]      = form["mundo"]
            s["ops"]        = form["ops"]
            s["puerto"]     = int(form["puerto"])
            break
    guardar_estado(data)

    dst = os.path.join(BASE_PATH, instancia)
    tpl = os.path.join(TEMPLATES, "minecraft", "docker-compose.yml")
    raw = open(tpl).read()
    ports = {"port_game": s["puerto"], "port_rcon": s["puerto"]+1}
    rendered = Template(raw).render(
        nombre_servidor=instancia,
        version=s["version"], memory=s["memory"],
        rcon_pass=s["rcon_pass"], descripcion=s["descripcion"],
        mundo=s["mundo"], ops=s["ops"], **ports
    )
    open(os.path.join(dst, "docker-compose.yml"), "w").write(rendered)
    subprocess.run(f"docker compose -f docker-compose.yml down", cwd=dst, shell=True)
    ejecutar_compose(dst, "up -d")
    return redirect(url_for("index"))

# —— Editar Zomboid ——
@app.route("/editar/zomboid/<instancia>")
@login_required
def editar_zomboid_form(instancia):
    data = cargar_estado()
    srv = next((s for s in data["zomboid"] if s["nombre"]==instancia), None)
    if not srv:
        return redirect(url_for("index"))
    mapas = ["TheIsland","ScorchedEarth_P","Aberration_P","Ragnarok","Extinction","Valguero_P"]
    return render_template("editar_zomboid.html", srv=srv, mapas=mapas)

@app.route("/editar/zomboid/<instancia>", methods=["POST"])
@login_required
def editar_zomboid(instancia):
    form = request.form
    data = cargar_estado()
    for s in data["zomboid"]:
        if s["nombre"] == instancia:
            s["mapa"]        = form["mapa"]
            s["mods"]        = form["mods"]
            s["password"]    = form["password"]
            s["public"]      = form["public"]
            s["max_players"] = form["max_players"]
            s["puerto"]      = int(form["puerto"])
            break
    guardar_estado(data)

    dst = os.path.join(BASE_PATH, instancia)
    envf = os.path.join(dst, ".env")
    lines = []
    for line in open(envf):
        if line.startswith("PZ_MAP="):
            lines.append(f'PZ_MAP="{s["mapa"]}"\n')
        elif line.startswith("PZ_MODS="):
            lines.append(f'PZ_MODS="{s["mods"]}"\n')
        elif line.startswith("PZ_PASSWORD="):
            lines.append(f'PZ_PASSWORD="{s["password"]}"\n')
        elif line.startswith("PZ_PUBLIC="):
            lines.append(f'PZ_PUBLIC={s["public"]}\n')
        elif line.startswith("PZ_MAX_PLAYERS="):
            lines.append(f'PZ_MAX_PLAYERS={s["max_players"]}\n')
        elif line.startswith("PZ_SERVER_PORT="):
            lines.append(f'PZ_SERVER_PORT={s["puerto"]}\n')
        else:
            lines.append(line)
    open(envf, "w").writelines(lines)

    subprocess.run(f"docker compose -f docker-compose.yml down", cwd=dst, shell=True)
    ejecutar_compose(dst, "up -d")
    return redirect(url_for("index"))

# —— Detener / Reiniciar / Borrar ——
@app.route("/detener/<instancia>")
@login_required
def detener(instancia):
    path = os.path.join(BASE_PATH, instancia)
    subprocess.run(f"docker compose -f {path}/docker-compose.yml down", cwd=BASE_PATH, shell=True)
    data = cargar_estado()
    for juego in data:
        for s in data[juego]:
            if s["nombre"] == instancia:
                s["estado"] = "parado"
    guardar_estado(data)
    return redirect(url_for("index"))

@app.route("/reiniciar/<instancia>")
@login_required
def reiniciar(instancia):
    path = os.path.join(BASE_PATH, instancia)
    subprocess.run(f"docker compose -f {path}/docker-compose.yml down", cwd=BASE_PATH, shell=True)
    subprocess.run(f"docker compose -f {path}/docker-compose.yml up -d", cwd=BASE_PATH, shell=True)
    data = cargar_estado()
    for juego in data:
        for s in data[juego]:
            if s["nombre"] == instancia:
                s["estado"] = "activo"
    guardar_estado(data)
    return redirect(url_for("index"))

@app.route("/borrar/<instancia>")
@login_required
def borrar(instancia):
    path = os.path.join(BASE_PATH, instancia)
    try:
        subprocess.run(
            f"docker compose -f {path}/docker-compose.yml down",
            shell=True, cwd=BASE_PATH, check=True
        )
    except subprocess.CalledProcessError as e:
        app.logger.error(f"Error al bajar {instancia}: {e}")
    try:
        shutil.rmtree(path)
    except Exception as e:
        app.logger.error(f"No se pudo eliminar {path}: {e}")
    data = cargar_estado()
    for juego in data:
        data[juego] = [srv for srv in data[juego] if srv["nombre"] != instancia]
    guardar_estado(data)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002)
