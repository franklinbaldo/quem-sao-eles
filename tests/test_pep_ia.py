"""Boundary tests for the Internet Archive publishing step.

Nothing here touches the network or a real credential: the point is to prove
that the pipeline behaves predictably at the boundary — silent when there is
nothing configured, loud when configuration is half-done, and deterministic
about where a given competency gets published.
"""

import hashlib
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import pep_pipeline as pipeline  # noqa: E402

FAKE = {"IA_ACCESS_KEY": "chave-de-teste", "IA_SECRET_KEY": "segredo-de-teste"}


def test_sem_credencial_e_silencioso():
    assert pipeline.ia_credentials({}) is None


def test_valor_em_branco_conta_como_ausente():
    assert pipeline.ia_credentials({"IA_ACCESS_KEY": "  ", "IA_SECRET_KEY": ""}) is None


@pytest.mark.parametrize("presente,faltando", [
    ("IA_ACCESS_KEY", "IA_SECRET_KEY"),
    ("IA_SECRET_KEY", "IA_ACCESS_KEY"),
])
def test_meia_credencial_falha_alto(presente, faltando):
    with pytest.raises(pipeline.CredencialIncompleta) as erro:
        pipeline.ia_credentials({presente: "valor"})
    assert faltando in str(erro.value)


def test_credencial_completa_e_devolvida_na_ordem():
    assert pipeline.ia_credentials(FAKE) == ("chave-de-teste", "segredo-de-teste")


def test_upload_nao_faz_nada_sem_credencial(tmp_path, capsys):
    """O boundary: sem credencial não há rede, nem leitura, nem exceção."""
    inexistente = tmp_path / "nao-existe.parquet"
    assert pipeline.upload_to_ia("202607", inexistente, "https://exemplo", env={}) is None
    assert "IA_ACCESS_KEY" in capsys.readouterr().out


def test_identificador_e_funcao_pura_da_competencia():
    assert pipeline.ia_identifier("202607") == "pep_br_data_2026"
    assert pipeline.ia_identifier("202601") == pipeline.ia_identifier("202612")
    assert pipeline.ia_remote_name("202607") == "202607_pep.parquet"


@pytest.mark.parametrize("ruim", ["2026", "2026-07", "abcdef", "", "20260712"])
def test_competencia_invalida_nao_vira_identificador(ruim):
    with pytest.raises(ValueError):
        pipeline.ia_identifier(ruim)


def test_proveniencia_descreve_o_arquivo_publicado(tmp_path):
    parquet = tmp_path / "202607_pep.parquet"
    parquet.write_bytes(b"conteudo-de-teste")
    prov = pipeline.build_provenance("202607", parquet, "https://portal/pep/202607")

    assert prov["identifier"] == "pep_br_data_2026"
    assert prov["arquivo"] == "202607_pep.parquet"
    assert prov["competencia"] == "2026-07"
    assert prov["origem"] == "https://portal/pep/202607"
    assert prov["sha256"] == hashlib.sha256(b"conteudo-de-teste").hexdigest()
    assert prov["md5"] == hashlib.md5(b"conteudo-de-teste").hexdigest()
    assert prov["size_bytes"] == len(b"conteudo-de-teste")
    json.dumps(prov)  # o JSON de proveniência precisa ser serializável


def test_proveniencia_nao_carrega_credencial(tmp_path, monkeypatch):
    monkeypatch.setenv("IA_ACCESS_KEY", "chave-que-nao-pode-vazar")
    parquet = tmp_path / "202607_pep.parquet"
    parquet.write_bytes(b"x")
    texto = json.dumps(pipeline.build_provenance("202607", parquet, "https://portal"))
    assert "chave-que-nao-pode-vazar" not in texto


def test_metadata_nao_reivindica_colecao():
    """Regressão: pedir `collection` explicitamente dá 403 numa conta comum.

    "Access Denied - You lack sufficient privileges to write to those
    collections" — o Internet Archive atribui a coleção sozinho.
    """
    meta = pipeline.build_item_metadata("2026")
    assert "collection" not in meta
    assert meta["mediatype"] == "data"
    assert "2026" in meta["title"]
    assert "2026" in meta["subject"]
