import gzip
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = Path(__file__).resolve().parent
DESTINO = BASE / "brasil_estados.geojson"

REGIOES = [
    "Norte",
    "Nordeste",
    "Centro-Oeste",
    "Sudeste",
    "Sul",
]

# Código IBGE: (sigla, nome, região)
UNIDADES = {
    "11": ("RO", "Rondônia", "Norte"),
    "12": ("AC", "Acre", "Norte"),
    "13": ("AM", "Amazonas", "Norte"),
    "14": ("RR", "Roraima", "Norte"),
    "15": ("PA", "Pará", "Norte"),
    "16": ("AP", "Amapá", "Norte"),
    "17": ("TO", "Tocantins", "Norte"),
    "21": ("MA", "Maranhão", "Nordeste"),
    "22": ("PI", "Piauí", "Nordeste"),
    "23": ("CE", "Ceará", "Nordeste"),
    "24": ("RN", "Rio Grande do Norte", "Nordeste"),
    "25": ("PB", "Paraíba", "Nordeste"),
    "26": ("PE", "Pernambuco", "Nordeste"),
    "27": ("AL", "Alagoas", "Nordeste"),
    "28": ("SE", "Sergipe", "Nordeste"),
    "29": ("BA", "Bahia", "Nordeste"),
    "31": ("MG", "Minas Gerais", "Sudeste"),
    "32": ("ES", "Espírito Santo", "Sudeste"),
    "33": ("RJ", "Rio de Janeiro", "Sudeste"),
    "35": ("SP", "São Paulo", "Sudeste"),
    "41": ("PR", "Paraná", "Sul"),
    "42": ("SC", "Santa Catarina", "Sul"),
    "43": ("RS", "Rio Grande do Sul", "Sul"),
    "50": ("MS", "Mato Grosso do Sul", "Centro-Oeste"),
    "51": ("MT", "Mato Grosso", "Centro-Oeste"),
    "52": ("GO", "Goiás", "Centro-Oeste"),
    "53": ("DF", "Distrito Federal", "Centro-Oeste"),
}


def obter_codigo(feature):
    propriedades = feature.get("properties") or {}
    candidatos = [
        propriedades.get("codarea"),
        propriedades.get("CD_UF"),
        propriedades.get("CD_GEOCUF"),
        feature.get("id"),
    ]

    for valor in candidatos:
        if valor is not None:
            codigo = str(valor).strip()
            if codigo in UNIDADES:
                return codigo

    raise ValueError(
        "Não foi possível identificar a UF. "
        f"Propriedades recebidas: {propriedades!r}"
    )


def carregar_geojson(resposta):
    conteudo = resposta.read()
    content_encoding = resposta.headers.get("Content-Encoding", "").lower()
    if content_encoding == "gzip" or conteudo.startswith(b"\x1f\x8b"):
        conteudo = gzip.decompress(conteudo)
    return json.loads(conteudo.decode("utf-8-sig"))


def main():
    parametros = urlencode({
        "formato": "application/vnd.geo+json",
        "qualidade": "minima",
        "intrarregiao": "UF",
    })
    url = (
        "https://servicodados.ibge.gov.br/api/v3/"
        f"malhas/paises/BR?{parametros}"
    )

    requisicao = Request(
        url,
        headers={
            "User-Agent": "MapaInterativoBrasil/1.0",
            "Accept": "application/geo+json, application/json",
        },
    )

    with urlopen(requisicao, timeout=120) as resposta:
        dados = carregar_geojson(resposta)

    if dados.get("type") != "FeatureCollection":
        raise ValueError("A resposta não é uma FeatureCollection GeoJSON.")

    features = dados.get("features")
    if not isinstance(features, list) or len(features) != 27:
        raise ValueError("Era esperado um arquivo com exatamente 27 UFs.")

    encontrados = set()

    for feature in features:
        codigo = obter_codigo(feature)

        if codigo in encontrados:
            raise ValueError(f"UF duplicada no arquivo: {codigo}")
        encontrados.add(codigo)

        geometria = feature.get("geometry") or {}
        if geometria.get("type") not in ("Polygon", "MultiPolygon"):
            raise ValueError(f"Geometria inválida para a UF {codigo}.")
        if not geometria.get("coordinates"):
            raise ValueError(f"Coordenadas ausentes na UF {codigo}.")

        uf, nome, regiao = UNIDADES[codigo]
        propriedades = feature.setdefault("properties", {})
        propriedades.update({
            "codigo_ibge": codigo,
            "uf": uf,
            "nome": nome,
            "regiao": regiao,
            "regiao_indice": REGIOES.index(regiao),
        })

    if encontrados != set(UNIDADES):
        raise ValueError("O conjunto de UFs está incompleto.")

    temporario = DESTINO.with_suffix(".geojson.tmp")
    temporario.write_text(
        json.dumps(dados, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    temporario.replace(DESTINO)

    print(f"Arquivo criado: {DESTINO}")
    print(f"UFs verificadas: {len(encontrados)}")
    print(f"Tamanho: {DESTINO.stat().st_size:,} bytes")


if __name__ == "__main__":
    try:
        main()
    except Exception as erro:
        raise SystemExit(
            f"Não foi possível preparar o GeoJSON: {erro}"
        ) from erro