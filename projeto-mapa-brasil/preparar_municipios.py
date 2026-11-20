import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import gzip

from preparar_geojson import UNIDADES

BASE = Path(__file__).resolve().parent
PASTA = BASE / "municipios"


def aneis_externos(geometria):
    if geometria["type"] == "Polygon":
        partes = [geometria["coordinates"]]
    else:
        partes = geometria["coordinates"]
    return [
        [[round(x, 4), round(y, 4)] for x, y in parte[0]]
        for parte in partes
    ]


def main():
    PASTA.mkdir(exist_ok=True)
    por_regiao = {}

    for codigo, (uf, nome_uf, regiao) in UNIDADES.items():
        print(f"Baixando {uf} - {nome_uf}...")
        params = urlencode({
            "formato": "application/vnd.geo+json",
            "qualidade": "minima",
            "intrarregiao": "municipio",
        })
        malha = baixar(
            f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{codigo}?{params}"
        )
        nomes_api = baixar(
            f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{uf}/municipios"
        )
        nomes = {str(m["id"]): m["nome"] for m in nomes_api}

        for feat in malha["features"]:
            cod = str((feat.get("properties") or {}).get("codarea", ""))
            por_regiao.setdefault(regiao, []).append({
                "nome": nomes.get(cod, cod),
                "uf": uf,
                "aneis": aneis_externos(feat["geometry"]),
            })

    for regiao, lista in por_regiao.items():
        destino = PASTA / f"{regiao}.json"
        destino.write_text(
            json.dumps(lista, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8",
        )
        print(f"{regiao}: {len(lista)} municípios -> {destino.name}")


def baixar(url, tentativas=3):
    req = Request(
        url,
        headers={
            "User-Agent": "MapaInterativoBrasil/1.0",
            "Accept": "application/json, application/geo+json",
            "Accept-Encoding": "identity",
        },
    )
    ultimo_erro = None
    for n in range(tentativas):
        try:
            with urlopen(req, timeout=180) as resp:
                bruto = resp.read()
            if bruto[:2] == b"\x1f\x8b":  # resposta veio em gzip
                bruto = gzip.decompress(bruto)
            return json.loads(bruto.decode("utf-8-sig"))
        except Exception as erro:
            ultimo_erro = erro
            print(f"  tentativa {n + 1} falhou: {erro}")
    raise ultimo_erro

if __name__ == "__main__":
    main()