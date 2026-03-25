from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import re
import time
import os
import json
import urllib3

# Suprime avisos de SSL — necessario em redes corporativas com proxy de inspecao SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import pytesseract
    import cv2
    import numpy as np
    from PIL import Image
    import io
    OCR_AVAILABLE = True
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except ImportError:
    OCR_AVAILABLE = False

app = Flask(__name__, static_folder=".")
CORS(app)

# =============================================
# API KEY — lida automaticamente do config.txt
# Para trocar: edite ou delete o config.txt
# =============================================
def load_api_key():
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.txt")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                print(f"  API Key carregada do config.txt ({key[:8]}...)")
                return key
    print("  [AVISO] config.txt nao encontrado — API Key nao configurada!")
    print("  Execute o start.bat para configurar sua API Key.")
    return ""

API_KEY = load_api_key()
# =============================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ATTACKS_FILE = os.path.join(BASE_DIR, "attacks.txt")

IP_REGEX = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b")

# PROTECTION_KEYWORDS removido — matching agora usa diretamente o attacks.txt
# via match_attack_from_list() com score de similaridade por palavras


@app.route("/")
def index():
    return send_from_directory(".", "index.html")

@app.route("/favicon.ico")
def favicon_ico():
    return send_from_directory(".", "favicon.ico", mimetype="image/vnd.microsoft.icon")

@app.route("/favicon.svg")
def favicon_svg():
    return send_from_directory(".", "favicon.svg", mimetype="image/svg+xml")

@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/check_ip")
def check_ip():
    ip = request.args.get("ip", "").strip()
    if not ip:
        return jsonify({"error": "IP nao fornecido"}), 400

    url = "https://api.abuseipdb.com/api/v2/check"
    headers = {"Accept": "application/json", "Key": API_KEY}
    # verbose necessario para retornar countryName (sem ele nao vem o nome do pais)
    # maxAgeInDays=365 para capturar totalReports do ultimo ano completo
    params = {"ipAddress": ip, "maxAgeInDays": 365, "verbose": ""}

    # Retry automatico: tenta 3 vezes com timeout crescente
    last_error = None
    for attempt in range(3):
        try:
            timeout = 15 + (attempt * 10)  # 15s, 25s, 35s
            print(f"[check_ip] IP={ip} tentativa={attempt+1}/3 timeout={timeout}s")
            response = requests.get(url, headers=headers, params=params, timeout=timeout, verify=False)
            print(f"[check_ip] IP={ip} status={response.status_code}")
            if response.status_code == 200:
                data = response.json()
                reports = data.get("data", {}).get("totalReports", "?")
                print(f"[check_ip] IP={ip} OK reports={reports}")
                # Remove array de reports detalhados — nao precisamos deles no frontend
                # Mantemos countryName (que so vem com verbose) e totalReports
                if "data" in data and "reports" in data["data"]:
                    del data["data"]["reports"]
                return jsonify(data)
            elif response.status_code == 429:
                print(f"[check_ip] IP={ip} RATE LIMIT")
                return jsonify({"error": "Rate limit atingido. Aguarde alguns segundos."}), 429
            else:
                last_error = f"Status {response.status_code}: {response.text[:100]}"
                print(f"[check_ip] IP={ip} erro: {last_error}")
        except requests.exceptions.Timeout:
            last_error = f"Timeout na tentativa {attempt + 1} ({timeout}s)"
            print(f"[check_ip] IP={ip} TIMEOUT tentativa {attempt+1}")
            time.sleep(2)
        except requests.exceptions.ConnectionError as e:
            last_error = f"Sem conexao: {str(e)[:80]}"
            print(f"[check_ip] IP={ip} CONNECTION ERROR: {last_error}")
            time.sleep(3)
        except Exception as e:
            last_error = str(e)
            print(f"[check_ip] IP={ip} EXCEPTION: {e}")
            time.sleep(1)

    return jsonify({"error": last_error or "Falha apos 3 tentativas"}), 500


@app.route("/attacks", methods=["GET"])
def get_attacks():
    try:
        if not os.path.exists(ATTACKS_FILE):
            return jsonify([])
        with open(ATTACKS_FILE, "r", encoding="utf-8") as f:
            attacks = [line.strip() for line in f if line.strip()]
        return jsonify(attacks)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/attacks", methods=["POST"])
def add_attack():
    data = request.get_json()
    attack = data.get("attack", "").strip() if data else ""
    if not attack:
        return jsonify({"error": "Ataque vazio"}), 400

    try:
        existing = []
        if os.path.exists(ATTACKS_FILE):
            with open(ATTACKS_FILE, "r", encoding="utf-8") as f:
                existing = [line.strip() for line in f if line.strip()]

        if attack in existing:
            return jsonify({"status": "exists", "attacks": existing})

        existing.append(attack)
        existing.sort()

        with open(ATTACKS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(existing) + "\n")

        return jsonify({"status": "added", "attacks": existing})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────────────────────
# REGEX: captura IPs dentro de parênteses  ex: (192.168.1.1)
#        OU IPs soltos (modo fallback / só-IPs)
# ─────────────────────────────────────────────────────────────
IP_IN_PARENS_REGEX = re.compile(r"\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)")


def load_attacks_list():
    """Carrega a lista de ataques do attacks.txt para uso no match de OCR."""
    try:
        if os.path.exists(ATTACKS_FILE):
            with open(ATTACKS_FILE, "r", encoding="utf-8") as f:
                return [line.strip() for line in f if line.strip()]
    except Exception:
        pass
    return []


def match_attack_from_list(text, attacks_list):
    """
    Compara o texto extraído do OCR com os ataques do attacks.txt.
    Retorna o ataque com maior pontuação de palavras em comum.
    Estratégia: conta quantas palavras do nome do ataque aparecem no texto OCR.
    """
    if not attacks_list or not text:
        return None

    text_lower = text.lower()
    best_attack = None
    best_score  = 0

    for attack in attacks_list:
        attack_lower = attack.lower()

        # Match exato tem prioridade máxima
        if attack_lower in text_lower:
            return attack

        # Pontuação por palavras em comum (ignora palavras curtas: over, the, of...)
        words = [w for w in re.split(r"\W+", attack_lower) if len(w) > 3]
        if not words:
            continue
        hits = sum(1 for w in words if w in text_lower)
        score = hits / len(words)  # proporção de palavras encontradas

        if score > best_score:
            best_score  = score
            best_attack = attack

    # Só aceita match se pelo menos 40% das palavras do ataque foram encontradas
    return best_attack if best_score >= 0.40 else None


def is_valid_public_ip(ip):
    """Valida se o IP é público e bem formado."""
    parts = ip.split(".")
    try:
        octets = [int(p) for p in parts]
    except ValueError:
        return False
    if not all(0 <= o <= 255 for o in octets):
        return False
    first, second = octets[0], octets[1]
    if first == 10 or first == 127:
        return False
    if first == 172 and 16 <= second <= 31:
        return False
    if first == 192 and second == 168:
        return False
    if first == 0 or first >= 224:
        return False
    return True


def prepare_image_versions(img):
    """
    Gera múltiplas versões pré-processadas da imagem para maximizar
    a taxa de acerto do Tesseract. Cada versão tem características
    diferentes e pode capturar IPs que outra perderia.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    versions = []

    # V1 — Cinza puro (baseline, boa para prints de alta resolução)
    versions.append(("gray_raw", gray))

    # V2 — Resize 2x + cinza (melhora muito prints de baixa resolução)
    upscaled = cv2.resize(gray, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    versions.append(("gray_2x", upscaled))

    # V3 — Binarização Otsu (preto/branco puro, fundo uniforme)
    _, otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(("otsu", otsu))

    # V4 — Binarização adaptativa (resolve fundo com iluminação irregular)
    adaptive = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )
    versions.append(("adaptive", adaptive))

    # V5 — Denoise + Otsu (remove ruído antes de binarizar)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    _, denoised_bin = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    versions.append(("denoised_otsu", denoised_bin))

    # V6 — Resize 2x + binarização adaptativa (melhor para prints pequenos com fundo irregular)
    adaptive_2x = cv2.adaptiveThreshold(
        upscaled, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 15, 3
    )
    versions.append(("adaptive_2x", adaptive_2x))

    return versions


def run_ocr_all_versions(versions):
    """
    Roda Tesseract em múltiplas versões da imagem e múltiplos PSMs.
    Retorna texto completo concatenado de todas as passagens.
    Usa image_to_data para filtrar por confiança mínima.
    """
    # Combinações de (versão, psm) — ordena do mais provável ao mais agressivo
    combos = [
        ("gray_2x",        6),   # bloco de texto limpo, imagem ampliada
        ("adaptive_2x",    6),   # binarizado + ampliado
        ("otsu",           6),   # preto/branco, bloco
        ("gray_raw",       4),   # coluna de texto variável
        ("adaptive",       4),   # adaptativo, coluna
        ("denoised_otsu",  6),   # sem ruído
        ("gray_raw",      11),   # texto esparso (varre tudo)
        ("gray_2x",       11),   # texto esparso ampliado
        ("adaptive_2x",   11),   # texto esparso binarizado
        ("gray_raw",       3),   # segmentação automática completa
    ]

    version_map = {name: img for name, img in versions}
    all_lines = []

    for (vname, psm) in combos:
        img_v = version_map.get(vname)
        if img_v is None:
            continue
        try:
            cfg = f"--oem 1 --psm {psm} --dpi 150"
            from pytesseract import Output as TessOutput
            data = pytesseract.image_to_data(img_v, config=cfg, output_type=TessOutput.DICT)

            # Reconstrói linhas agrupando palavras com confiança >= 50
            line_words = {}
            for i, word in enumerate(data["text"]):
                word = word.strip()
                if not word:
                    continue
                conf = int(data["conf"][i])
                if conf < 50:
                    continue
                line_num  = data["line_num"][i]
                block_num = data["block_num"][i]
                key = (block_num, line_num)
                line_words.setdefault(key, []).append(word)

            for key in sorted(line_words.keys()):
                line = " ".join(line_words[key])
                if line:
                    all_lines.append(line)

        except Exception as e:
            print(f"[OCR] versao={vname} psm={psm} erro: {e}")
            continue

    return all_lines


@app.route("/extract_image", methods=["POST"])
def extract_image():
    if not OCR_AVAILABLE:
        return jsonify({"error": "Tesseract nao instalado"}), 500

    file = request.files.get("image")
    if not file:
        return jsonify({"error": "Nenhuma imagem recebida"}), 400

    # Modo de extração: "full" (IP + ataque) ou "ips_only" (só IPs)
    mode = request.form.get("mode", "full").strip().lower()

    try:
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({"error": "Imagem invalida"}), 400

        # Pré-processa imagem em múltiplas versões
        versions = prepare_image_versions(img)

        # Roda OCR em todas as versões e consolida linhas
        all_lines = run_ocr_all_versions(versions)

        # Carrega lista de ataques do arquivo para matching
        attacks_list = load_attacks_list()

        results_map = {}  # ip -> {ip, protection}

        for line in all_lines:
            line = line.strip()
            if not line:
                continue

            # Ignora linhas que são objetos já existentes no Check Point
            if re.match(r"Host_", line, re.IGNORECASE):
                continue

            # ── Extrai IPs dentro de parênteses ──────────────────────
            # Regra principal: só captura IPs que estejam dentro de ()
            # Ex: "SQL Injection (192.168.1.1) bla bla" → captura 192.168.1.1
            ips_in_parens = IP_IN_PARENS_REGEX.findall(line)

            # ── Fallback para modo só-IPs ─────────────────────────────
            # Se o modo for "ips_only", aceita qualquer IP válido na linha,
            # independente de estar ou não em parênteses
            if mode == "ips_only":
                ips_raw = IP_REGEX.findall(line)
                ips_to_process = list(dict.fromkeys(ips_in_parens + ips_raw))
            else:
                ips_to_process = ips_in_parens

            if not ips_to_process:
                continue

            for ip in ips_to_process:
                if ip in results_map:
                    continue
                if not is_valid_public_ip(ip):
                    continue

                # Determina o protection name
                if mode == "ips_only":
                    # Modo só-IPs: não tenta descobrir ataque
                    protection = "Atividade Suspeita"
                else:
                    # Modo full: tenta fazer match com attacks.txt
                    protection = match_attack_from_list(line, attacks_list)
                    if not protection:
                        # Tenta nas linhas vizinhas (contexto ±2 linhas)
                        idx = all_lines.index(line) if line in all_lines else -1
                        if idx >= 0:
                            context = " ".join(all_lines[max(0, idx-2):idx+3])
                            protection = match_attack_from_list(context, attacks_list)
                    if not protection:
                        protection = "Atividade Suspeita"

                results_map[ip] = {"ip": ip, "protection": protection}
                print(f"[OCR] IP capturado: {ip} | protection: {protection} | linha: {line[:80]}")

        results = list(results_map.values())
        print(f"[OCR] Total extraido: {len(results)} IPs | modo: {mode}")
        return jsonify(results)

    except Exception as e:
        print(f"[OCR] ERRO GERAL: {e}")
        return jsonify({"error": str(e)}), 500
    
@app.route("/check_ipinfo")
def check_ipinfo():
    ip = request.args.get("ip", "").strip()
    if not ip:
        return jsonify({"error": "IP nao fornecido"}), 400

    url = f"https://ipinfo.io/{ip}/json"
    try:
        response = requests.get(url, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            # Extrai ASN e nome do campo "org" (ex: "AS13335 Cloudflare, Inc.")
            org = data.get("org", "")
            asn = ""
            asn_name = ""
            if org:
                parts = org.split(" ", 1)
                if parts[0].startswith("AS"):
                    asn = parts[0]
                    asn_name = parts[1] if len(parts) > 1 else ""
            return jsonify({
                "city":     data.get("city", ""),
                "region":   data.get("region", ""),
                "country":  data.get("country", ""),
                "org":      org,
                "asn":      asn,
                "asnName":  asn_name,
                "hostname": data.get("hostname", ""),
                "timezone": data.get("timezone", ""),
            })
        else:
            return jsonify({"error": f"Status {response.status_code}"}), response.status_code
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    print("\n" + "=" * 55)
    print("  SOC IP Analyzer v5.5 — Servidor iniciado!")
    print("  Acesse: http://127.0.0.1:5000")
    print(f"  API Key: {'configurada' if API_KEY else 'NAO CONFIGURADA — edite config.txt'}")
    print(f"  OCR disponivel: {'SIM' if OCR_AVAILABLE else 'NAO (instale o Tesseract)'}")
    print("=" * 55 + "\n")
    app.run(host="127.0.0.1", port=5000, debug=False)
