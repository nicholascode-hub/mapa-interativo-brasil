import json
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np
import pygame

from engine import GestureEngine
from data import BRAZIL_REGIONS

BASE = Path(__file__).resolve().parent
GEOJSON = BASE / "brasil_estados.geojson"
PASTA_MUN = BASE / "municipios"

BG_MAP = (40, 44, 52)
VIEW_RECT = pygame.Rect(375, 35, 860, 430)
ZOOM_MUNICIPIOS = 3.4
COS_LAT = np.cos(np.radians(14.0))
INICIAR_EM_TELA_CHEIA = True


# ----------------------------------------------------------------- câmera
def abrir_camera():
    tentativas = [
        (0, cv2.CAP_DSHOW), (0, cv2.CAP_MSMF),
        (1, cv2.CAP_DSHOW), (1, cv2.CAP_MSMF),
        (0, cv2.CAP_ANY),
    ]
    for idx, backend in tentativas:
        cap = cv2.VideoCapture(idx, backend)
        if not cap.isOpened():
            cap.release()
            continue
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        inicio = time.time()
        while time.time() - inicio < 4:
            ok, frame = cap.read()
            if ok and frame is not None:
                print(f"Câmera OK: índice {idx}, backend {backend}")
                return cap
            time.sleep(0.1)
        cap.release()
    return None


# ------------------------------------------------------------------- mapa
def carregar_mapa():
    if not GEOJSON.exists():
        print("GeoJSON não encontrado. Rode: python preparar_geojson.py")
        pygame.quit()
        sys.exit(1)

    dados = json.loads(GEOJSON.read_text(encoding="utf-8"))
    estados = {}
    for feat in dados["features"]:
        props = feat["properties"]
        geom = feat["geometry"]
        partes = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        polys = []
        for parte in partes:
            anel = np.array(parte[0], dtype=np.float64)
            polys.append(np.column_stack([anel[:, 0] * COS_LAT, -anel[:, 1]]))
        estados[props["uf"]] = {"regiao": props["regiao"], "polys": polys}
    return estados


def bbox(polys):
    todos = np.vstack(polys)
    return todos.min(axis=0), todos.max(axis=0)


def enquadrar(polys, view):
    mn, mx = bbox(polys)
    centro = (mn + mx) / 2
    tam = np.maximum(mx - mn, 1e-6)
    escala = min(view.width / tam[0], view.height / tam[1]) * 0.9
    return centro, escala


def escurecer(cor, fator=0.35):
    return tuple(int(c * fator + b * (1 - fator)) for c, b in zip(cor, BG_MAP))


def carregar_municipios(regiao):
    arq = PASTA_MUN / f"{regiao}.json"
    if not arq.exists():
        print(f"AVISO: {arq} não encontrado. Rode preparar_municipios.py")
        return []
    lista = []
    for m in json.loads(arq.read_text(encoding="utf-8")):
        polys = []
        for anel in m["aneis"]:
            a = np.array(anel, dtype=np.float64)
            polys.append(np.column_stack([a[:, 0] * COS_LAT, -a[:, 1]]))
        mn, mx = bbox(polys)
        lista.append({"nome": m["nome"], "uf": m["uf"], "polys": polys, "mn": mn, "mx": mx})
    return lista


# ------------------------------------------------------------------- main
def main():
    pygame.init()
    flags = pygame.SCALED | pygame.RESIZABLE
    if INICIAR_EM_TELA_CHEIA:
        flags |= pygame.FULLSCREEN
    screen = pygame.display.set_mode((1280, 720), flags)
    pygame.display.set_caption("Mapa Interativo do Brasil - Visão Computacional")
    clock = pygame.time.Clock()

    estados = carregar_mapa()
    regions_list = list(BRAZIL_REGIONS.keys())

    todos_polys = [p for e in estados.values() for p in e["polys"]]
    centro_br, escala_br = enquadrar(todos_polys, VIEW_RECT)
    enquadros = {}
    for nome in regions_list:
        polys = [p for e in estados.values() if e["regiao"] == nome for p in e["polys"]]
        enquadros[nome] = enquadrar(polys, VIEW_RECT)

    rotulos = {}
    for uf, e in estados.items():
        maior = max(e["polys"], key=len)
        mn, mx = bbox([maior])
        rotulos[uf] = (mn + mx) / 2

    municipios = {n: carregar_municipios(n) for n in regions_list}
    print("Municípios carregados:", {n: len(v) for n, v in municipios.items()})
    cam_w, cam_h = 640, 480

    cam_centro = centro_br.copy()
    cam_escala = escala_br

    hands = mp.solutions.hands.Hands(
        max_num_hands=1, min_detection_confidence=0.7, min_tracking_confidence=0.7
    )
    cap = abrir_camera()
    if cap is None:
        print("AVISO: câmera indisponível. Rodando no modo teclado.")
    ultimo_frame_ok = time.time()

    engine = GestureEngine()
    idx = 0
    ponteiro_suave = None

    font_title = pygame.font.SysFont("arial", 28, bold=True)
    font_body = pygame.font.SysFont("arial", 20)
    font_small = pygame.font.SysFont("arial", 16)
    font_uf = pygame.font.SysFont("arial", 14, bold=True)

    cam_surface = pygame.Surface((320, 240))
    cam_surface.fill((20, 20, 20))

    running = True
    while running:
        # --- eventos ---
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_RIGHT:
                    idx = (idx + 1) % len(regions_list)
                elif event.key == pygame.K_LEFT:
                    idx = (idx - 1) % len(regions_list)
                elif event.key == pygame.K_r:
                    engine.reset_zoom()
                elif event.key in (pygame.K_F11, pygame.K_f):
                    pygame.display.toggle_fullscreen()

        # zoom contínuo pelo teclado (segurar ↑ ou ↓)
        teclas = pygame.key.get_pressed()
        if teclas[pygame.K_UP]:
            engine.zoom = min(engine.max_zoom, engine.zoom + 0.04)
        if teclas[pygame.K_DOWN]:
            engine.zoom = max(engine.min_zoom, engine.zoom - 0.04)

        # --- câmera e gestos ---
        landmarks_np = None
        if cap is not None:
            ok, frame = cap.read()
            if ok and frame is not None:
                ultimo_frame_ok = time.time()
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                cam_w, cam_h = w, h
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                res = hands.process(rgb)
                if res.multi_hand_landmarks:
                    landmarks_np = engine.to_pixels(
                        res.multi_hand_landmarks[0].landmark, w, h
                    )
                    for x, y in landmarks_np:
                        cv2.circle(rgb, (int(x), int(y)), 4, (0, 255, 0), -1)
                cam_surface = pygame.transform.scale(
                    pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB"), (320, 240)
                )
            elif time.time() - ultimo_frame_ok > 5:
                print("AVISO: câmera parou. Seguindo no modo teclado.")
                cap.release()
                cap = None
                cam_surface.fill((20, 20, 20))

        state = engine.process(landmarks_np)
        if state["action"] == "next":
            idx = (idx + 1) % len(regions_list)
        elif state["action"] == "previous":
            idx = (idx - 1) % len(regions_list)
        elif state["action"] == "quit":
            running = False

        nome = regions_list[idx]
        data = BRAZIL_REGIONS[nome]

        # --- câmera do mapa (suave) ---
        t = float(np.clip((engine.zoom - 0.8) / (engine.max_zoom - 0.8), 0, 1))
        centro_reg, escala_reg = enquadros[nome]
        alvo_escala = escala_br * (escala_reg / escala_br) ** t
        alvo_centro = centro_br * (1 - t) + centro_reg * t
        cam_escala += (alvo_escala - cam_escala) * 0.12
        cam_centro = cam_centro + (alvo_centro - cam_centro) * 0.12

        # --- renderização ---
        screen.fill((30, 30, 35))
        screen.blit(cam_surface, (20, 20))
        if cap is None:
            screen.blit(font_small.render("Sem câmera (use ← →)", True, (255, 120, 120)), (60, 125))

        mostrar_mun = engine.zoom >= ZOOM_MUNICIPIOS and len(municipios[nome]) > 0

        status = pygame.Rect(20, 280, 320, 420)
        pygame.draw.rect(screen, (45, 45, 55), status, border_radius=10)
        pygame.draw.rect(screen, (70, 70, 90), status, 2, border_radius=10)
        texts = [
            f"Gesto: {state['gesture'].upper()}",
            f"Zoom: {engine.zoom:.2f}x",
            f"Ação: {state['action'] or 'Nenhuma'}",
            f"Municípios: {'VISÍVEIS' if mostrar_mun else 'ocultos (zoom ≥ 3.4)'}",
            "",
            "Controles:",
            "• Mão aberta (Swipe): Muda Região",
            "• Pinça + Polegar: Zoom no Mapa",
            "• Indicador: seleciona município",
            "• Punho fechado (1.5s): Sair",
            "• Teclado: ← → região, ↑ ↓ zoom",
            "• R: reseta zoom | F11: tela cheia",
            "• ESC: sai",
        ]
        for i, txt in enumerate(texts):
            cor = (255, 255, 255) if i < 4 else (200, 200, 200)
            screen.blit(font_small.render(txt, True, cor), (35, 300 + i * 25))

        moldura = pygame.Rect(360, 20, 890, 680)
        pygame.draw.rect(screen, BG_MAP, moldura, border_radius=12)
        pygame.draw.rect(screen, (60, 68, 82), moldura, 3, border_radius=12)

        screen.set_clip(VIEW_RECT)
        pygame.draw.rect(screen, (34, 38, 46), VIEW_RECT)
        origem = np.array(VIEW_RECT.center, dtype=np.float64)

        def para_tela(pts):
            return ((pts - cam_centro) * cam_escala + origem).astype(int).tolist()

        # estados: inativos primeiro, ativos por cima
        for ativo in (False, True):
            for uf, e in estados.items():
                if (e["regiao"] == nome) != ativo:
                    continue
                if ativo and mostrar_mun:
                    continue  # os municípios substituem os estados ativos
                cor_base = BRAZIL_REGIONS[e["regiao"]]["color"]
                cor = cor_base if ativo else escurecer(cor_base)
                for poly in e["polys"]:
                    pts = para_tela(poly)
                    if len(pts) < 3:
                        continue
                    pygame.draw.polygon(screen, cor, pts)
                    pygame.draw.polygon(
                        screen, (255, 255, 255) if ativo else (20, 22, 28), pts, 2 if ativo else 1
                    )

        # municípios
        selecionado = None
        ponteiro = None
        if mostrar_mun:
            if state["gesture"] in ("point", "zoom") and state["pointer"] is not None:
                alvo = np.array([
                    VIEW_RECT.x + state["pointer"][0] / cam_w * VIEW_RECT.width,
                    VIEW_RECT.y + state["pointer"][1] / cam_h * VIEW_RECT.height,
                ])
                ponteiro_suave = alvo if ponteiro_suave is None else ponteiro_suave + (alvo - ponteiro_suave) * 0.35
                ponteiro = (float(ponteiro_suave[0]), float(ponteiro_suave[1]))
            else:
                ponteiro_suave = None
                mx_, my_ = pygame.mouse.get_pos()
                if VIEW_RECT.collidepoint(mx_, my_):
                    ponteiro = (float(mx_), float(my_))

            cor_reg = BRAZIL_REGIONS[nome]["color"]
            cor_mun = tuple(int(c * 0.8) for c in cor_reg)
            for m in municipios[nome]:
                (x0, y0), (x1, y1) = para_tela(np.array([m["mn"], m["mx"]]))
                if x1 < VIEW_RECT.left or x0 > VIEW_RECT.right or y1 < VIEW_RECT.top or y0 > VIEW_RECT.bottom:
                    continue
                for poly in m["polys"]:
                    pts = para_tela(poly)
                    if len(pts) < 3:
                        continue
                    pygame.draw.polygon(screen, cor_mun, pts)
                    pygame.draw.polygon(screen, (235, 235, 235), pts, 1)
                    if ponteiro and x0 <= ponteiro[0] <= x1 and y0 <= ponteiro[1] <= y1:
                        if cv2.pointPolygonTest(np.array(pts, dtype=np.int32), ponteiro, False) >= 0:
                            selecionado = (m, pts)

            if selecionado:
                m, pts = selecionado
                cor_sel = tuple(min(255, int(c * 0.5 + 255 * 0.5)) for c in cor_reg)
                pygame.draw.polygon(screen, cor_sel, pts)
                pygame.draw.polygon(screen, (255, 255, 255), pts, 3)

            if ponteiro:
                pygame.draw.circle(screen, (255, 80, 80), (int(ponteiro[0]), int(ponteiro[1])), 5)

        # siglas dos estados (só sem municípios)
        if not mostrar_mun:
            for uf, e in estados.items():
                if e["regiao"] != nome:
                    continue
                px, py = para_tela(rotulos[uf][None, :])[0]
                if VIEW_RECT.collidepoint(px, py):
                    s = font_uf.render(uf, True, (255, 255, 255))
                    sombra = font_uf.render(uf, True, (0, 0, 0))
                    screen.blit(sombra, (px - s.get_width() // 2 + 1, py - s.get_height() // 2 + 1))
                    screen.blit(s, (px - s.get_width() // 2, py - s.get_height() // 2))

        # nome do município selecionado
        if selecionado and ponteiro:
            m, _ = selecionado
            txt = font_body.render(f"{m['nome']} - {m['uf']}", True, (255, 255, 255))
            caixa = txt.get_rect().inflate(20, 12)
            caixa.topleft = (int(ponteiro[0]) + 15, int(ponteiro[1]) - 40)
            caixa.clamp_ip(VIEW_RECT)
            pygame.draw.rect(screen, (20, 22, 28), caixa, border_radius=6)
            pygame.draw.rect(screen, (255, 255, 255), caixa, 1, border_radius=6)
            screen.blit(txt, (caixa.x + 10, caixa.y + 6))

        screen.set_clip(None)

        screen.blit(font_title.render(f"Região {nome}", True, (255, 255, 255)), (395, 45))
        screen.blit(
            font_small.render("Estados: " + ", ".join(data["states"]), True, (220, 220, 220)),
            (395, 82),
        )

        info = pygame.Rect(390, 480, 830, 190)
        pygame.draw.rect(screen, (30, 34, 40), info, border_radius=8)
        pygame.draw.rect(screen, (80, 90, 110), info, 1, border_radius=8)
        screen.blit(font_body.render(data["desc"], True, (255, 230, 150)), (410, 500))
        screen.blit(font_small.render("Fauna: " + " • ".join(data["fauna"]), True, (150, 220, 255)), (410, 545))
        screen.blit(font_small.render("Flora: " + " • ".join(data["flora"]), True, (150, 255, 180)), (410, 580))
        screen.blit(
            font_small.render(f"Região {idx + 1} de {len(regions_list)}", True, (180, 180, 180)),
            (410, 625),
        )

        pygame.display.flip()
        clock.tick(30)

    if cap is not None:
        cap.release()
    hands.close()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()