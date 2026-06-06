"""
============================================================
  CLASIFICADOR DE GATOS Y PERROS — VERSIÓN 3
  Dataset descargado desde la nube (GitHub)
  Tema 3 · Subtema 33 · Clasificación de Imágenes

  CÓMO CONFIGURAR TU PROPIO REPOSITORIO EN GITHUB:
  
  1. Crea un repositorio público en GitHub
  2. Sube imágenes a carpetas gato/ y perro/
  3. Crea dataset.json con el formato indicado abajo
  4. Reemplaza URL_DATASET con la URL raw de tu archivo
============================================================

INSTALACIÓN:
    pip install flask pillow

EJECUCIÓN:
    python v3_nube_github.py

LUEGO abre:  http://127.0.0.1:5000
"""

from flask import Flask, render_template_string, request, jsonify
import io, math, json, random, urllib.request, urllib.error

app = Flask(__name__)

# ══════════════════════════════════════════════════════════════
#  CONFIGURACIÓN — Cambia esta URL por la de tu repositorio
#
#  Formato esperado del dataset.json:
#  [
#    {
#      "nombre": "gato_01.jpg",
#      "etiqueta": "gato",
#      "url": "https://raw.githubusercontent.com/TU_USUARIO/TU_REPO/main/gato/gato_01.jpg"
#    },
#    ...
#  ]
# ══════════════════════════════════════════════════════════════
URL_DATASET = (
    "https://raw.githubusercontent.com/MiguelAHR/dataset-gatos-perros/main/dataset.json"
)

# Cache en memoria para no descargar en cada clasificación
_cache_dataset = None
_cache_mensaje = None

# ══════════════════════════════════════════════════════════════
#  EXTRACTOR DE CARACTERÍSTICAS (10 características)
# ══════════════════════════════════════════════════════════════
def _std(valores, media):
    if len(valores) < 2:
        return 0.0
    return math.sqrt(sum((x - media) ** 2 for x in valores) / len(valores))

def extraer_caracteristicas(imagen_bytes):
    """Extrae 10 características de una imagen en bytes."""
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(imagen_bytes)).convert("RGB").resize((64, 64))
        pixeles = list(img.getdata())

        r_vals = [p[0] / 255.0 for p in pixeles]
        g_vals = [p[1] / 255.0 for p in pixeles]
        b_vals = [p[2] / 255.0 for p in pixeles]

        media_r = sum(r_vals) / len(r_vals)
        media_g = sum(g_vals) / len(g_vals)
        media_b = sum(b_vals) / len(b_vals)

        brillo    = 0.299 * media_r + 0.587 * media_g + 0.114 * media_b
        todos     = r_vals + g_vals + b_vals
        contraste = max(todos) - min(todos)
        std_r     = _std(r_vals, media_r)
        std_g     = _std(g_vals, media_g)
        std_b     = _std(b_vals, media_b)

        saturaciones = [max(r,g,b) - min(r,g,b) for r,g,b in zip(r_vals,g_vals,b_vals)]
        saturacion   = sum(saturaciones) / len(saturaciones)

        diferencias = [abs((r_vals[i]+g_vals[i]+b_vals[i]) - (r_vals[i+1]+g_vals[i+1]+b_vals[i+1])) / 3.0
                       for i in range(len(r_vals) - 64)]
        textura = sum(diferencias) / len(diferencias) if diferencias else 0.0

        return [round(v, 4) for v in [media_r, media_g, media_b, brillo,
                                       contraste, std_r, std_g, std_b, saturacion, textura]]
    except Exception:
        return [round(random.uniform(0.3, 0.7), 4) for _ in range(10)]

# ══════════════════════════════════════════════════════════════
#  DESCARGA DE IMÁGENES DESDE GITHUB
# ══════════════════════════════════════════════════════════════
def descargar_url(url, timeout=15):
    """Descarga el contenido de una URL como bytes."""
    req = urllib.request.Request(
        url, headers={"User-Agent": "ClasificadorGatosPerros/3.0"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()

def cargar_dataset_nube(forzar_recarga=False):
    """
    Descarga el dataset.json y luego cada imagen desde GitHub.
    Usa cache para no volver a descargar si ya se cargó antes.
    Retorna (dataset, mensaje_info) o (None, mensaje_error).
    """
    global _cache_dataset, _cache_mensaje

    if _cache_dataset is not None and not forzar_recarga:
        return _cache_dataset, _cache_mensaje

    try:
        print(f"\n🌐 Descargando dataset.json desde:\n   {URL_DATASET}")
        lista_raw = descargar_url(URL_DATASET, timeout=10)
        lista     = json.loads(lista_raw.decode("utf-8"))

        if not isinstance(lista, list) or len(lista) == 0:
            return None, "❌ El dataset.json está vacío o tiene formato incorrecto."

        print(f"📋 {len(lista)} imágenes en el dataset. Descargando...")

        dataset  = []
        errores  = 0

        for item in lista:
            nombre   = item.get("nombre", "sin_nombre")
            etiqueta = item.get("etiqueta", "").lower()
            url_img  = item.get("url", "")

            if etiqueta not in ("gato", "perro"):
                print(f"  ⚠️ Etiqueta desconocida en '{nombre}': {etiqueta}")
                errores += 1
                continue

            try:
                print(f"  ⬇️  {nombre} ({etiqueta})...", end=" ", flush=True)
                img_bytes = descargar_url(url_img, timeout=15)
                caract    = extraer_caracteristicas(img_bytes)
                dataset.append({
                    "nombre":          nombre,
                    "etiqueta":        etiqueta,
                    "url":             url_img,
                    "caracteristicas": caract,
                })
                print("✅")
            except urllib.error.HTTPError as e:
                errores += 1
                print(f"❌ HTTP {e.code}")
            except Exception as e:
                errores += 1
                print(f"❌ {str(e)[:40]}")

        if not dataset:
            return None, "❌ No se pudo descargar ninguna imagen. Revisa las URLs."

        gatos  = sum(1 for m in dataset if m["etiqueta"] == "gato")
        perros = sum(1 for m in dataset if m["etiqueta"] == "perro")
        ok_msg = f"✅ {len(dataset)} imágenes reales desde GitHub ({gatos} 🐱 · {perros} 🐶)"
        if errores:
            ok_msg += f" — {errores} errores ignorados"

        print(f"\n📊 Listo: {gatos} gatos + {perros} perros")
        _cache_dataset = dataset
        _cache_mensaje = ok_msg
        return dataset, ok_msg

    except urllib.error.URLError as e:
        return None, f"❌ Sin conexión o URL incorrecta: {e.reason}"
    except json.JSONDecodeError:
        return None, "❌ El dataset.json no tiene formato JSON válido."
    except Exception as e:
        return None, f"❌ Error inesperado: {str(e)}"

# ══════════════════════════════════════════════════════════════
#  CLASIFICADOR KNN
# ══════════════════════════════════════════════════════════════
PESOS = [1.0, 1.0, 1.2, 1.0, 1.5, 0.8, 0.8, 0.8, 2.0, 1.8]

def distancia_ponderada(a, b):
    return math.sqrt(sum(PESOS[i] * (a[i] - b[i]) ** 2 for i in range(len(a))))

def clasificar_knn(caracteristicas, dataset, k=5):
    k = min(k, len(dataset))
    distancias = [(distancia_ponderada(caracteristicas, m["caracteristicas"]),
                   m["etiqueta"], m["nombre"], m.get("url",""))
                  for m in dataset]
    distancias.sort(key=lambda x: x[0])
    vecinos   = distancias[:k]
    etiquetas = [e for _, e, _, _ in vecinos]
    conteo    = {"gato": etiquetas.count("gato"), "perro": etiquetas.count("perro")}
    prediccion = max(conteo, key=conteo.get)
    confianza  = conteo[prediccion] / k * 100

    top3 = etiquetas[:3]
    if len(top3) == 3 and all(e == prediccion for e in top3):
        confianza = min(confianza + 10, 100)

    vecinos_info = [{"nombre": n, "etiqueta": e, "url": u}
                    for _, e, n, u in vecinos]
    return prediccion, confianza, conteo, vecinos_info

# ══════════════════════════════════════════════════════════════
#  PLANTILLA HTML — Versión 3
# ══════════════════════════════════════════════════════════════
HTML_V3 = """
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>V3 · Clasificador Gatos & Perros · Nube GitHub</title>
<style>
  :root{--cat:#f97316;--dog:#3b82f6;--bg:#0f172a;--card:#1e293b;--text:#e2e8f0;--accent:#b45309}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:'Segoe UI',sans-serif;min-height:100vh}
  header{background:linear-gradient(135deg,#1c0a00,#7c2d12);padding:1.5rem 2rem;text-align:center}
  header h1{font-size:1.9rem;font-weight:800}
  header p{opacity:.75;margin-top:.4rem;font-size:.95rem}
  .version-badge{display:inline-block;background:#b45309;color:#fef9c3;padding:.3rem 1rem;
    border-radius:9999px;font-weight:700;font-size:.85rem;margin-top:.6rem}
  .main{max-width:800px;margin:0 auto;padding:1.5rem}
  .card{background:var(--card);border-radius:1rem;padding:1.5rem;margin-bottom:1.2rem;border:1px solid #334155}
  .card h2{font-size:1.05rem;font-weight:700;margin-bottom:.8rem;color:#fde68a}
  label{display:block;font-size:.9rem;color:#94a3b8;margin-bottom:.4rem}
  input[type=file]{width:100%;padding:.6rem;background:#0f172a;border:2px dashed #92400e;
                   border-radius:.5rem;color:var(--text);cursor:pointer}
  input[type=file]:hover{border-color:#f59e0b}
  .btn{padding:.7rem 1.8rem;border-radius:.6rem;border:none;font-weight:700;cursor:pointer;
       font-size:1rem;transition:all .2s;margin:.2rem}
  .btn-orange{background:#b45309;color:#fff}.btn-orange:hover{background:#d97706}
  .btn-reload{background:#334155;color:#fff;font-size:.85rem;padding:.5rem 1rem}
  .btn-reload:hover{background:#475569}
  .result-box{border-radius:.8rem;padding:1.5rem;margin-top:1rem;text-align:center;display:none}
  .result-box.gato{background:rgba(249,115,22,.15);border:2px solid var(--cat)}
  .result-box.perro{background:rgba(59,130,246,.15);border:2px solid var(--dog)}
  .result-label{font-size:2.8rem;font-weight:900;margin:.4rem 0}
  .result-label.gato{color:var(--cat)}.result-label.perro{color:var(--dog)}
  .result-conf{font-size:.95rem;opacity:.8;margin-bottom:1rem}
  .progress{height:14px;border-radius:7px;background:#172033;margin:.3rem 0;overflow:hidden}
  .progress-bar{height:100%;border-radius:7px;transition:width .7s}
  .bar-cat{background:var(--cat)}.bar-dog{background:var(--dog)}
  .info-box{background:#1c0a00;border-left:4px solid #f59e0b;border-radius:.4rem;
            padding:.8rem 1rem;margin:.6rem 0;font-size:.87rem;line-height:1.7;color:#fde68a}
  .step{display:flex;gap:.8rem;align-items:flex-start;margin:.5rem 0;font-size:.87rem}
  .step-num{background:#b45309;color:#fff;border-radius:50%;min-width:24px;height:24px;
            display:flex;align-items:center;justify-content:center;font-size:.8rem}
  .preview-img{max-width:220px;max-height:220px;border-radius:.6rem;margin:.8rem 0;
               display:none;border:3px solid #f59e0b}
  .spinner{display:none;width:36px;height:36px;border:4px solid #334155;
           border-top-color:#f59e0b;border-radius:50%;animation:spin .7s linear infinite;margin:.8rem auto}
  @keyframes spin{to{transform:rotate(360deg)}}
  .status-ok{color:#4ade80}.status-err{color:#f87171}
  code{background:#1e293b;padding:.1rem .4rem;border-radius:.2rem;font-size:.82rem;color:#fde68a}
  .vecinos-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:.5rem;margin-top:.8rem}
  .vecino-card{background:#1c0a00;border-radius:.5rem;padding:.5rem;text-align:center;font-size:.75rem}
  .vecino-img{width:60px;height:60px;object-fit:cover;border-radius:.3rem;margin-bottom:.3rem}
  .json-box{background:#0f172a;border-radius:.4rem;padding:.8rem;font-family:'Courier New',monospace;
            font-size:.78rem;color:#fde68a;overflow-x:auto;line-height:1.5;border:1px solid #92400e}
  table{width:100%;border-collapse:collapse;font-size:.82rem}
  th{background:#1c0a00;padding:.5rem .6rem;text-align:left;color:#fde68a;border-bottom:1px solid #92400e}
  td{padding:.4rem .6rem;border-bottom:1px solid #1e293b}
  tr:hover td{background:#1c0a00}
  .badge-gato{background:#7c3aed;color:#ede9fe;padding:.1rem .5rem;border-radius:9999px;font-size:.75rem}
  .badge-perro{background:#1e40af;color:#dbeafe;padding:.1rem .5rem;border-radius:9999px;font-size:.75rem}
  footer{text-align:center;padding:1.5rem;color:#475569;font-size:.82rem;border-top:1px solid #1e293b}
</style>
</head>
<body>

<header>
  <h1>🐱 Clasificador de Gatos & Perros 🐶</h1>
  <p>Tema 3 · Subtema 33 · Clasificación de Imágenes con Flask</p>
  <div class="version-badge">☁️ VERSIÓN 3 — Dataset desde GitHub (Nube)</div>
</header>

<div class="main">

  <!-- Instrucciones GitHub -->
  <div class="card">
    <h2>☁️ Configuración del repositorio en GitHub</h2>
    <div class="info-box">
      URL actual del dataset: <code>{{ url_dataset }}</code>
    </div>
    <div class="step"><div class="step-num">1</div>
      <div>Crea un repositorio <strong>público</strong> en GitHub</div></div>
    <div class="step"><div class="step-num">2</div>
      <div>Crea las carpetas <code>gato/</code> y <code>perro/</code> y sube imágenes .jpg</div></div>
    <div class="step"><div class="step-num">3</div>
      <div>Crea <code>dataset.json</code> en la raíz con este formato:</div></div>
    <div class="json-box" style="margin:.6rem 0 .6rem 2rem">[
  {
    "nombre": "gato_01.jpg",
    "etiqueta": "gato",
    "url": "https://raw.githubusercontent.com/USUARIO/REPO/main/gato/gato_01.jpg"
  },
  {
    "nombre": "perro_01.jpg",
    "etiqueta": "perro",
    "url": "https://raw.githubusercontent.com/USUARIO/REPO/main/perro/perro_01.jpg"
  }
]</div>
    <div class="step"><div class="step-num">4</div>
      <div>Copia la URL <strong>raw</strong> de tu dataset.json y reemplaza
      <code>URL_DATASET</code> en el archivo Python</div></div>
    <br>
    <button class="btn btn-orange" onclick="probarConexion()">🌐 Probar conexión y cargar dataset</button>
    <button class="btn btn-reload" onclick="recargar()">🔄 Recargar (forzar nueva descarga)</button>
    <div id="estado-nube" style="margin-top:.8rem;display:none" class="info-box"></div>
  </div>

  <!-- Clasificar -->
  <div class="card">
    <h2>🔍 Clasificar imagen con imágenes reales de GitHub</h2>
    <div class="info-box">
      El clasificador descargará las imágenes de GitHub, extraerá sus características
      y las comparará con la tuya usando <strong>KNN ponderado k=5</strong>.
      La primera carga puede tardar unos segundos.
    </div>
    <label>Sube una imagen de gato o perro:</label>
    <input type="file" id="fileInput" accept="image/*" onchange="previewImage()">
    <img id="preview" class="preview-img">
    <br><br>
    <button class="btn btn-orange" onclick="clasificar()">🔍 Clasificar con imágenes reales</button>
    <div class="spinner" id="spinner"></div>
    <div id="spinner-msg" style="text-align:center;font-size:.85rem;color:#94a3b8;margin-top:.4rem;display:none">
      Descargando imágenes de GitHub… puede tardar hasta 30 segundos la primera vez.
    </div>

    <div class="result-box" id="resultado">
      <div id="res-emoji" style="font-size:4rem"></div>
      <div class="result-label" id="res-label"></div>
      <div class="result-conf" id="res-conf"></div>
      <div style="margin-top:.8rem">
        <div style="display:flex;justify-content:space-between;font-size:.85rem">
          <span>🐱 Gato</span><span id="pcat"></span></div>
        <div class="progress"><div class="progress-bar bar-cat" id="bar-cat" style="width:0%"></div></div>
        <div style="display:flex;justify-content:space-between;font-size:.85rem;margin-top:.4rem">
          <span>🐶 Perro</span><span id="pdog"></span></div>
        <div class="progress"><div class="progress-bar bar-dog" id="bar-dog" style="width:0%"></div></div>
      </div>
      <div id="vecinos-display"></div>
    </div>
  </div>

</div>

<footer>
  Versión 3 · Dataset en GitHub · Imágenes reales · KNN ponderado k=5 · Python + Flask<br>
  <small style="opacity:.6">Tema 3 · Subtema 33 · Clasificación de Imágenes</small>
</footer>

<script>
function previewImage() {
  const file = document.getElementById('fileInput').files[0];
  const img  = document.getElementById('preview');
  if (!file) { img.style.display='none'; return; }
  const reader = new FileReader();
  reader.onload = e => { img.src = e.target.result; img.style.display='block'; };
  reader.readAsDataURL(file);
}

async function probarConexion(forzar=false) {
  const box = document.getElementById('estado-nube');
  box.style.display = 'block';
  box.innerHTML = '⏳ Descargando imágenes de GitHub…';
  const url = forzar ? '/probar_nube?reload=1' : '/probar_nube';
  const r = await fetch(url);
  const d = await r.json();
  box.style.borderColor = d.ok ? '#22c55e' : '#ef4444';
  box.innerHTML = d.ok
    ? `<span class="status-ok">✅ ${d.mensaje}</span>`
    : `<span class="status-err">❌ ${d.error}</span>`;
}

function recargar() { probarConexion(true); }

async function clasificar() {
  const fileInput = document.getElementById('fileInput');
  if (!fileInput.files[0]) { alert('Selecciona una imagen primero'); return; }

  document.getElementById('spinner').style.display = 'block';
  document.getElementById('spinner-msg').style.display = 'block';
  document.getElementById('resultado').style.display  = 'none';

  const formData = new FormData();
  formData.append('imagen', fileInput.files[0]);

  const resp = await fetch('/clasificar', { method:'POST', body: formData });
  const data = await resp.json();
  document.getElementById('spinner').style.display = 'none';
  document.getElementById('spinner-msg').style.display = 'none';

  if (data.error) { alert('Error: ' + data.error); return; }

  const esCato = data.prediccion === 'gato';
  const res = document.getElementById('resultado');
  res.className = 'result-box ' + data.prediccion;
  document.getElementById('res-emoji').textContent = esCato ? '😸' : '🐕';
  const lbl = document.getElementById('res-label');
  lbl.className = 'result-label ' + data.prediccion;
  lbl.textContent = data.prediccion.toUpperCase();
  document.getElementById('res-conf').textContent =
    `Confianza: ${data.confianza.toFixed(1)}%  ·  ${data.n_muestras} imágenes reales desde GitHub  ·  k=5`;

  const total = data.votos.gato + data.votos.perro;
  document.getElementById('pcat').textContent = (data.votos.gato/total*100).toFixed(0)+'%';
  document.getElementById('pdog').textContent = (data.votos.perro/total*100).toFixed(0)+'%';
  document.getElementById('bar-cat').style.width = (data.votos.gato/total*100)+'%';
  document.getElementById('bar-dog').style.width = (data.votos.perro/total*100)+'%';

  // Vecinos más cercanos con miniatura si hay URL
  if (data.vecinos) {
    let html = '<p style="font-size:.83rem;color:#94a3b8;margin-top:.8rem">5 vecinos más cercanos:</p>';
    html += '<div class="vecinos-grid">';
    data.vecinos.forEach(v => {
      const col   = v.etiqueta === 'gato' ? '#7c3aed' : '#1d4ed8';
      const emoji = v.etiqueta === 'gato' ? '🐱' : '🐶';
      const imgTag = v.url
        ? `<img src="${v.url}" class="vecino-img" onerror="this.style.display='none'">`
        : `<div style="font-size:2.5rem">${emoji}</div>`;
      html += `<div class="vecino-card" style="border:1px solid ${col}">
        ${imgTag}
        <div style="color:#94a3b8;word-break:break-all">${v.nombre}</div>
        <div style="color:${col};font-weight:700">${emoji} ${v.etiqueta}</div>
      </div>`;
    });
    html += '</div>';
    document.getElementById('vecinos-display').innerHTML = html;
  }
  res.style.display = 'block';
}
</script>
</body>
</html>
"""

# ══════════════════════════════════════════════════════════════
#  RUTAS FLASK
# ══════════════════════════════════════════════════════════════
@app.route("/")
def index():
    return render_template_string(HTML_V3, url_dataset=URL_DATASET)

@app.route("/probar_nube")
def probar_nube():
    forzar = request.args.get("reload") == "1"
    if forzar:
        global _cache_dataset, _cache_mensaje
        _cache_dataset = None
        _cache_mensaje = None
    dataset, info = cargar_dataset_nube()
    if dataset is None:
        return jsonify({"ok": False, "error": info})
    return jsonify({"ok": True, "mensaje": info})

@app.route("/clasificar", methods=["POST"])
def clasificar():
    archivo = request.files.get("imagen")
    if not archivo:
        return jsonify({"error": "No se recibió imagen"})

    dataset, error = cargar_dataset_nube()
    if dataset is None:
        return jsonify({"error": error})

    imagen_bytes    = archivo.read()
    caracteristicas = extraer_caracteristicas(imagen_bytes)
    prediccion, confianza, votos, vecinos = clasificar_knn(caracteristicas, dataset, k=5)

    return jsonify({
        "prediccion": prediccion,
        "confianza":  confianza,
        "votos":      votos,
        "n_muestras": len(dataset),
        "vecinos":    vecinos,
    })

# ══════════════════════════════════════════════════════════════
#  INICIO
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 58)
    print("  CLASIFICADOR V3 — Dataset en GitHub (Nube)")
    print(f"  URL: {URL_DATASET}")
    print("=" * 58)
    print("  Requiere repositorio GitHub con dataset.json")
    print("  y carpetas gato/ y perro/ con imágenes.")
    print()
    print("  Abre:  http://127.0.0.1:5000")
    print("=" * 58)
    app.run(debug=True, port=5000)
