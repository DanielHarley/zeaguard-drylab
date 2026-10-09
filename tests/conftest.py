"""Shared fixtures. The NB03 CP0 real-data run is executed once per session into a temporary directory."""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
HAS_TSA = (ROOT / "data/external/tsa.GITV.1.fsa_nt.gz").is_file()
HAS_SUPPLEMENT = (ROOT / "data/external/Dalaison-Fuentes2023_S1_mmc1.pdf").is_file()
HAS_BLAST = all(shutil.which(tool) for tool in ("blastn", "tblastn", "blastp", "makeblastdb", "blastdbcmd"))


@pytest.fixture(scope="session")
def cp0_result(tmp_path_factory):
    if not (HAS_TSA and HAS_SUPPLEMENT and HAS_BLAST):
        pytest.skip("needs the hash-pinned TSA, the 2023 supplement and BLAST+")
    from zeaguard import nb03_cp0

    out = tmp_path_factory.mktemp("nb03_cp0")
    return {"result": nb03_cp0.run_cp0(ROOT, out), "out": out}
