# Mapa Interativo do Brasil

Aplicação interativa que mostra as regiões e os estados do Brasil e, com zoom,
os municípios. A navegação pode ser feita por gestos capturados pela webcam ou
pelo teclado.

## Requisitos

- Python 3.9 a 3.12
- Webcam para os controles por gestos (opcional; sem ela, use o teclado)

O código usa a API `solutions` do MediaPipe, indisponível nas versões
compatíveis com Python 3.13 ou superior. Por isso, o ambiente está limitado
a Python 3.9–3.12.

## Preparação e execução

Execute os comandos na ordem abaixo, a partir da pasta do projeto. Os scripts
`preparar_geojson.py` e `preparar_municipios.py` precisam de acesso à internet
para baixar as malhas e os nomes dos municípios nas APIs do IBGE.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python preparar_geojson.py
python preparar_municipios.py
python main.py
```

Os scripts de preparação geram `brasil_estados.geojson` e os arquivos JSON em
`municipios/`. Esses dados gerados são ignorados pelo Git; execute os scripts
novamente em cada instalação.

## Webcam e privacidade

A webcam é usada para reconhecer gestos. Os frames são processados localmente
pela aplicação e não são gravados nem enviados. Não há captura ou processamento
de webcam durante a preparação dos dados. Se a câmera não estiver disponível,
a aplicação continua no modo teclado: setas para navegar e ajustar o zoom,
`R` para redefinir o zoom e `ESC` para sair.

## Fonte e uso dos dados

As malhas geográficas e os nomes dos municípios são obtidos das APIs do
Instituto Brasileiro de Geografia e Estatística (IBGE):

- [API de malhas territoriais](https://servicodados.ibge.gov.br/api/docs/malhas?versao=3)
- [API de localidades](https://servicodados.ibge.gov.br/api/docs/localidades)

Fonte a citar: **IBGE — Instituto Brasileiro de Geografia e Estatística**.
Os dados do IBGE são de terceiros e não estão cobertos pela licença MIT deste
código. Consulte os termos e metadados do IBGE antes de redistribuir os dados
ou utilizá-los em outros contextos.

## Licença

O código deste projeto está sob a licença MIT. Consulte [LICENSE](LICENSE).
