import os
import sys
import zipfile
import tempfile
import datetime
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

def upload_to_ia(ym: str, parquet_path: Path):
    import internetarchive as ia
    # Requires secrets in env: IA_ACCESS_KEY, IA_SECRET_KEY
    if "IA_ACCESS_KEY" not in os.environ:
        print("Skipping IA upload (no credentials)")
        return

    year = ym[:4]
    identifier = f"pep_br_data_{year}"

    print(f"Uploading to Internet Archive item: {identifier}...")

    item = ia.get_item(identifier)

    metadata = {
        "title": f"PEP - Portal da Transparencia - {year}",
        "mediatype": "data",
        "creator": "Controladoria-Geral da União (CGU)",
        "description": "Pessoas Expostas Politicamente - Dados Abertos Brasil"
    }

    r = item.upload(
        str(parquet_path),
        metadata=metadata,
        access_key=os.environ["IA_ACCESS_KEY"],
        secret_key=os.environ["IA_SECRET_KEY"],
        verbose=True
    )
    print("Upload complete!")

if __name__ == "__main__":
    out_dir = Path("public/data")
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        url, ym = get_latest_pep_url()
        parquet_file = process_pep_data(url, ym, out_dir)
        # upload_to_ia(ym, parquet_file) # Disabled by default unless keys are present
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
