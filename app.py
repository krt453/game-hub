#!/usr/bin/env python3
import os
import json
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
    UserMixin,
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# ─────── Configuración básica ───────
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cámbiala_por_una_clave_segura")

# Configuración de base de datos
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///data/gamehub.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

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


# ─────── Modelos ───────
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    game = db.Column(db.String(20))
    data = db.Column(db.Text)  # JSON con configuraciones específicas
    estado = db.Column(db.String(20), default="parado")


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Crear la base de datos y usuario admin por defecto
with app.app_context():
    db.create_all()
    if not User.query.first():
        admin = User(username="admin", is_admin=True)
        admin.set_password("admin")
        db.session.add(admin)
        db.session.commit()

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
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user)
            return redirect(url_for("index"))
        flash("Usuario o contraseña incorrectos.", "error")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        if User.query.filter_by(username=u).first():
            flash("El usuario ya existe", "error")
        else:
            user = User(username=u)
            user.set_password(p)
            db.session.add(user)
            db.session.commit()
            flash("Cuenta creada. Inicia sesión", "success")
            return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ─────── RUTA PRINCIPAL ───────
@app.route("/")
@login_required
def index():
    servers = {"ark": [], "minecraft": [], "zomboid": []}
    for srv in Server.query.all():
        data = json.loads(srv.data)
        data["estado"] = srv.estado
        if srv.game in servers:
            servers[srv.game].append(data)
    return render_template("index.html", servers=servers)


# ─────── Gestión de servidores ───────


def save_server(game, data, estado="parado"):
    srv = Server(nombre=data["nombre"], game=game, data=json.dumps(data), estado=estado)
    db.session.add(srv)
    db.session.commit()


def update_server(srv, data):
    srv.data = json.dumps(data)
    db.session.commit()


@app.route("/nuevo_ark", methods=["GET", "POST"])
@login_required
def nuevo_ark():
    if request.method == "POST":
        data = {
            "nombre": request.form["nombre"],
            "mapa": request.form["mapa"],
            "mods": request.form.get("mods", ""),
            "adminpass": request.form.get("adminpass", ""),
            "cluster": request.form.get("cluster", ""),
            "max_players": request.form.get("max_players", "20"),
            "puerto": 7787,
        }
        save_server("ark", data)
        flash("Servidor ARK creado", "success")
        return redirect(url_for("index"))
    return render_template("crear_ark.html")


@app.route("/nuevo_minecraft", methods=["GET", "POST"])
@login_required
def nuevo_minecraft():
    if request.method == "POST":
        data = {
            "nombre": request.form["nombre"],
            "version": request.form["version"],
            "memory": request.form.get("memory", "1024"),
            "rcon_pass": request.form.get("rcon_pass", ""),
            "descripcion": request.form.get("descripcion", ""),
            "mundo": request.form.get("mundo", "world"),
            "ops": request.form.get("ops", ""),
            "puerto": 25565,
        }
        save_server("minecraft", data)
        flash("Servidor Minecraft creado", "success")
        return redirect(url_for("index"))
    return render_template("crear_minecraft.html")


@app.route("/nuevo_zomboid", methods=["GET", "POST"])
@login_required
def nuevo_zomboid():
    if request.method == "POST":
        data = {
            "nombre": request.form["nombre"],
            "mapa": request.form.get("mapa", "TaintedRemnants"),
            "mods": request.form.get("mods", ""),
            "password": request.form.get("password", ""),
            "public": request.form.get("public", "1"),
            "max_players": request.form.get("max_players", "10"),
            "puerto": 16261,
        }
        save_server("zomboid", data)
        flash("Servidor Zomboid creado", "success")
        return redirect(url_for("index"))
    return render_template("crear_zomboid.html")


def get_server_or_404(game, nombre):
    srv = Server.query.filter_by(game=game, nombre=nombre).first_or_404()
    data = json.loads(srv.data)
    return srv, data


@app.route("/editar/ark/<nombre>", methods=["GET", "POST"])
@login_required
def editar_ark(nombre):
    srv, data = get_server_or_404("ark", nombre)
    if request.method == "POST":
        data["mapa"] = request.form.get("mapa", data["mapa"])
        data["mods"] = request.form.get("mods", "")
        data["cluster"] = request.form.get("cluster", "")
        data["puerto"] = int(request.form.get("puerto", data.get("puerto", 7787)))
        update_server(srv, data)
        flash("Cambios guardados", "success")
        return redirect(url_for("index"))
    return render_template("editar_ark.html", srv=data)


@app.route("/editar/minecraft/<nombre>", methods=["GET", "POST"])
@login_required
def editar_minecraft(nombre):
    srv, data = get_server_or_404("minecraft", nombre)
    if request.method == "POST":
        data["version"] = request.form.get("version", data["version"])
        data["memory"] = request.form.get("memory", data["memory"])
        data["rcon_pass"] = request.form.get("rcon_pass", "")
        data["descripcion"] = request.form.get("descripcion", "")
        data["mundo"] = request.form.get("mundo", "world")
        data["ops"] = request.form.get("ops", "")
        data["puerto"] = int(request.form.get("puerto", data.get("puerto", 25565)))
        update_server(srv, data)
        flash("Cambios guardados", "success")
        return redirect(url_for("index"))
    return render_template("editar_minecraft.html", srv=data)


@app.route("/editar/zomboid/<nombre>", methods=["GET", "POST"])
@login_required
def editar_zomboid(nombre):
    srv, data = get_server_or_404("zomboid", nombre)
    if request.method == "POST":
        data["mapa"] = request.form.get("mapa", data["mapa"])
        data["mods"] = request.form.get("mods", "")
        data["password"] = request.form.get("password", "")
        data["public"] = request.form.get("public", data.get("public", "1"))
        data["max_players"] = request.form.get("max_players", data["max_players"])
        data["puerto"] = int(request.form.get("puerto", data.get("puerto", 16261)))
        update_server(srv, data)
        flash("Cambios guardados", "success")
        return redirect(url_for("index"))
    return render_template("editar_zomboid.html", srv=data)


@app.route("/borrar/<nombre>")
@login_required
def borrar(nombre):
    srv = Server.query.filter_by(nombre=nombre).first_or_404()
    db.session.delete(srv)
    db.session.commit()
    flash("Servidor eliminado", "info")
    return redirect(url_for("index"))


def change_state(nombre, estado):
    srv = Server.query.filter_by(nombre=nombre).first_or_404()
    srv.estado = estado
    db.session.commit()


@app.route("/iniciar/<nombre>")
@login_required
def iniciar(nombre):
    change_state(nombre, "activo")
    flash("Servidor iniciado", "success")
    return redirect(url_for("index"))


@app.route("/detener/<nombre>")
@login_required
def detener(nombre):
    change_state(nombre, "parado")
    flash("Servidor detenido", "info")
    return redirect(url_for("index"))


@app.route("/reiniciar/<nombre>")
@login_required
def reiniciar(nombre):
    change_state(nombre, "activo")
    flash("Servidor reiniciado", "success")
    return redirect(url_for("index"))


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
            "enable_leave_msg": False,
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
        cfg["server_name"] = request.form.get("server_name", cfg["server_name"])
        cfg["server_password"] = request.form.get("server_password", "")
        cfg["admin_password"] = request.form.get("admin_password", "")
        cfg["map_name"] = request.form.get("map_name", cfg["map_name"])
        cfg["enable_3rd_person"] = bool(request.form.get("enable_3rd_person"))
        cfg["enable_crosshair"] = bool(request.form.get("enable_crosshair"))
        cfg["disable_pvp"] = bool(request.form.get("disable_pvp"))
        cfg["enable_hardcore"] = bool(request.form.get("enable_hardcore"))
        cfg["enable_join_msg"] = bool(request.form.get("enable_join_msg"))
        cfg["enable_leave_msg"] = bool(request.form.get("enable_leave_msg"))
        save_server_config(instancia, cfg)
        flash("⚙️ Configuración guardada correctamente.", "success")
        return redirect(url_for("server_config", instancia=instancia))

    # Mapas preinstalados (puedes ampliarlos o leer dinámicamente)
    mapas_pre = ["The Island", "The Lost World", "Apako Islands", "IceAge"]
    return render_template(
        "server_config.html", instancia=instancia, cfg=cfg, mapas_pre=mapas_pre
    )


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
