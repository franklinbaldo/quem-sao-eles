import datetime
import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

import httpx
import ibis
from pydantic import BaseModel, Field

# Ensure we use duckdb backend
ibis.set_backend("duckdb")

class PepRow(BaseModel):
    cpf: str = Field(alias="CPF")
    nome: str = Field(alias="Nome_PEP")
    sigla_funcao: str = Field(alias="Sigla_Função")
    descricao_funcao: str = Field(alias="Descrição_Função")
    nivel_funcao: str = Field(alias="Nível_Função")
    nome_orgao: str = Field(alias="Nome_Órgão")
    data_inicio_exercicio: str = Field(alias="Data_Início_Exercício")
    data_fim_exercicio: str = Field(alias="Data_Fim_Exercício")
    data_fim_carencia: str = Field(alias="Data_Fim_Carência")

def get_latest_pep_url() -> str:
    # Portal da Transparencia format: 202401_PEP.zip (YearMonth)
    # They update monthly. Let's find the most recent available.
    now = datetime.datetime.now()
    # Try current month and previous months
    for i in range(4):
        date = now - datetime.timedelta(days=i * 30)
        ym = date.strftime("%Y%m")
        url = f"https://portaldatransparencia.gov.br/download-de-dados/pep/{ym}"
        # The URL redirects to the actual zip
        try:
            resp = httpx.head(url, follow_redirects=True, timeout=10.0)
            if resp.status_code == 200:
                print(f"Found latest PEP data for {ym}: {resp.url}")
                return str(resp.url), ym
        except Exception as e:
            pass
    raise Exception("Could not find a valid PEP dataset URL.")

def process_pep_data(zip_url: str, ym: str, output_dir: Path):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_zip = Path(tmpdir) / f"{ym}_PEP.zip"
        print(f"Downloading {zip_url} to {tmp_zip}...")

        with httpx.stream("GET", zip_url) as r:
            with open(tmp_zip, "wb") as f:
                for chunk in r.iter_bytes():
                    f.write(chunk)

        print(f"Extracting {tmp_zip}...")
        with zipfile.ZipFile(tmp_zip, 'r') as zip_ref:
            zip_ref.extractall(tmpdir)

        csv_files = list(Path(tmpdir).glob("*.csv"))
        if not csv_files:
            raise Exception("No CSV found in the ZIP.")
        csv_file = csv_files[0]
        print(f"Found CSV: {csv_file}")

        # Load via Ibis
        print("Loading and converting to Parquet via Ibis...")
        # read_csv handles standard pandas/duckdb kwargs
        # The Portal CSV is usually iso-8859-1 or latin1, separated by ';'
        # Let's read via ibis, but since duckdb backend might complain about 'latin1',
        # we can just not specify the encoding (let DuckDB infer) or use 'ISO-8859-1' if needed.
        # Actually DuckDB wants standard names, or we can convert it manually if it fails.
        # It says: invalid unicode. We can try setting `ignore_errors=True` or `encoding='ISO-8859-1'`
        try:
            t = ibis.read_csv(str(csv_file), sep=";", encoding="ISO-8859-1")
        except Exception:
            # Fallback if duckdb doesn't like the encoding kwarg
            t = ibis.read_csv(str(csv_file), sep=";", ignore_errors=True)

        # We can clean/standardize column names to be english/lowercase
        col_mapping = {
            "CPF": "cpf",
            "Nome_PEP": "nome",
            "Sigla_Função": "sigla_funcao",
            "Descrição_Função": "descricao_funcao",
            "Nível_Função": "nivel_funcao",
            "Nome_Órgão": "nome_orgao",
            "Data_Início_Exercício": "data_inicio_exercicio",
            "Data_Fim_Exercício": "data_fim_exercicio",
            "Data_Fim_Carência": "data_fim_carencia"
        }

        # Keep only columns that exist (in case of schema changes)
        # We need to make sure the original columns map correctly. If the header wasn't read, duckdb might name them 'column0', etc.
        # But we did read with header. However, if the encoding causes issues, let's fix column names properly.
        actual_cols = t.columns

        # Since Ibis with DuckDB might drop headers if not properly read, let's check
        # In our test, actual_cols returned values from the first row because the header was dropped
        # We can enforce header=True

        # Let's fix column names by overriding them since header parsing is weird with this file
        try:
            t = ibis.read_csv(str(csv_file), sep=";", encoding="ISO-8859-1", header=True)
        except Exception:
            t = ibis.read_csv(str(csv_file), sep=";", ignore_errors=True, header=True)

        # We know the fixed standard columns for this file.
        fixed_names = [
            "cpf", "nome", "sigla_funcao", "descricao_funcao",
            "nivel_funcao", "nome_orgao", "data_inicio_exercicio",
            "data_fim_exercicio", "data_fim_carencia"
        ]

        # Only rename what is available
        actual_cols = t.columns
        rename_dict = {fixed_names[i]: actual_cols[i] for i in range(min(len(fixed_names), len(actual_cols)))}
        t = t.rename(rename_dict)

        out_file = output_dir / f"{ym}_pep.parquet"
        t.to_parquet(str(out_file))
        print(f"Successfully wrote Parquet to {out_file}")
        return out_file

# --- Internet Archive ---------------------------------------------------------
#
# Contrato de arquivamento: um item por ANO, `pep_br_data_<ano>`, que agrega
# todos os snapshots mensais daquele ano como arquivos separados. A competência
# vive no nome do arquivo (`202607_pep.parquet`), não no identificador, porque
# a CGU republica a base todo mês e o valor está na série, não no recorte.
#
# Tanto o identificador quanto o nome do arquivo remoto são funções puras da
# competência: o mesmo mês sempre aponta para o mesmo endereço público.

IA_ACCESS_ENV = "IA_ACCESS_KEY"
IA_SECRET_ENV = "IA_SECRET_KEY"


class CredencialIncompleta(RuntimeError):
    """Só metade da credencial foi configurada — erro de configuração, não ausência."""


def ia_identifier(ym: str) -> str:
    if not (len(ym) == 6 and ym.isdigit()):
        raise ValueError(f"competência inválida: {ym!r}")
    return f"pep_br_data_{ym[:4]}"


def ia_remote_name(ym: str) -> str:
    return f"{ym}_pep.parquet"


def ia_credentials(env=None):
    """(access, secret) quando as duas existem, None quando nenhuma existe.

    Metade configurada é erro: significa que alguém quis publicar e o segredo
    não chegou. Falhar aqui é mais barato do que descobrir depois que o mês
    não foi arquivado.
    """
    env = os.environ if env is None else env
    access = (env.get(IA_ACCESS_ENV) or "").strip()
    secret = (env.get(IA_SECRET_ENV) or "").strip()
    if access and secret:
        return access, secret
    if access or secret:
        faltando = IA_SECRET_ENV if access else IA_ACCESS_ENV
        raise CredencialIncompleta(
            f"{faltando} não está definida; configure as duas ou nenhuma."
        )
    return None


def file_digests(path: Path) -> dict:
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            md5.update(chunk)
            sha256.update(chunk)
    return {"md5": md5.hexdigest(), "sha256": sha256.hexdigest(),
            "size_bytes": path.stat().st_size}


def build_provenance(ym: str, parquet_path: Path, source_url: str) -> dict:
    return {
        "schema": "pep-snapshot-provenance-v1",
        "competencia": f"{ym[:4]}-{ym[4:]}",
        "identifier": ia_identifier(ym),
        "arquivo": ia_remote_name(ym),
        "origem": source_url,
        "fonte": "Controladoria-Geral da União (CGU) — Portal da Transparência",
        "coletado_em": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0).isoformat(),
        **file_digests(parquet_path),
    }


def build_item_metadata(year: str) -> dict:
    """Metadados do item anual.

    Sem `collection`: uma conta comum não tem privilégio de escrever direto em
    coleção nomeada (403 "You lack sufficient privileges to write to those
    collections"). O Internet Archive faz a atribuição sozinho.
    """
    return {
        "title": f"PEP — Portal da Transparência — {year}",
        "mediatype": "data",
        "creator": "Controladoria-Geral da União (CGU)",
        "subject": ["pep", "brasil", "transparencia", "dados-abertos", year],
        "language": "por",
        "description": (
            "Pessoas Expostas Politicamente — dados abertos do Portal da "
            f"Transparência (CGU). Um arquivo Parquet por competência de {year}, "
            "acompanhado do respectivo JSON de proveniência."
        ),
    }


def upload_to_ia(ym: str, parquet_path: Path, source_url: str, env=None):
    """Publica o snapshot do mês no item anual. Devolve o identificador ou None.

    Idempotente: se o arquivo já está lá com o mesmo md5, não reenvia. Se está
    lá com conteúdo diferente, não sobrescreve por conta própria — um snapshot
    já publicado é um endereço que outras pessoas podem estar citando.
    """
    env = os.environ if env is None else env
    creds = ia_credentials(env)
    if creds is None:
        print(f"Sem {IA_ACCESS_ENV}/{IA_SECRET_ENV}: snapshot fica só no repositório.")
        return None
    access_key, secret_key = creds

    import internetarchive as ia

    identifier = ia_identifier(ym)
    remote_name = ia_remote_name(ym)
    digests = file_digests(parquet_path)

    item = ia.get_item(identifier)
    remoto = next((f for f in item.files if f.get("name") == remote_name), None)
    if remoto is not None:
        if remoto.get("md5") == digests["md5"]:
            print(f"{identifier}/{remote_name} já publicado e idêntico; nada a fazer.")
            return identifier
        if (env.get("IA_ALLOW_OVERWRITE") or "").strip() != "1":
            print(
                f"{identifier}/{remote_name} já existe com conteúdo diferente. "
                "Não sobrescrevendo (defina IA_ALLOW_OVERWRITE=1 para forçar)."
            )
            return identifier

    provenance = build_provenance(ym, parquet_path, source_url)
    year = ym[:4]
    with tempfile.TemporaryDirectory() as tmpdir:
        prov_path = Path(tmpdir) / f"{ym}_pep.provenance.json"
        prov_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2),
                             encoding="utf-8")
        print(f"Enviando {remote_name} para archive.org/details/{identifier} ...")
        item.upload(
            {remote_name: str(parquet_path), prov_path.name: str(prov_path)},
            metadata=build_item_metadata(year),
            access_key=access_key,
            secret_key=secret_key,
            retries=3,
            verbose=True,
        )
    print(f"Publicado: https://archive.org/download/{identifier}/{remote_name}")
    return identifier


if __name__ == "__main__":
    out_dir = Path("public/data")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        url, ym = get_latest_pep_url()
        parquet_file = process_pep_data(url, ym, out_dir)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    # O Parquet já está em disco: a partir daqui uma falha não custa o snapshot,
    # então ela pode (e deve) ser barulhenta.
    upload_to_ia(ym, parquet_file, url)
