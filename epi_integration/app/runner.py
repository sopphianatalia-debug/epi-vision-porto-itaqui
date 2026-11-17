"""
Orquestrador de processos para os testes de integração da Fase 3.5.

POR QUE SUBPROCESSOS (e não import direto em um único processo Python):
--------------------------------------------------------------------
Cada um dos módulos (epi_fusion, epi_rules, epi_incident, epi_identity,
epi_ppe, epi_compliance) define seu próprio pacote de nível superior chamado
`app`. Isso é correto e intencional dentro de cada módulo (independência,
Dockerfile próprio, deploy isolado) — mas significa que NÃO é possível
importar `epi_fusion/app` e `epi_rules/app` no mesmo processo Python: o
segundo import substituiria o primeiro em `sys.modules["app"]`.

A Fase 3.5 foi explícita: não alterar a arquitetura existente e não
reimplementar os serviços. Em vez de renomear pacotes (o que tocaria em todos
os módulos) optamos por subir cada serviço como um processo `uvicorn`
independente, com seu próprio cwd/PYTHONPATH, e falar com eles por HTTP —
exatamente como aconteceria em produção (cada um tem Dockerfile próprio).
Isso também torna o teste de integração mais honesto: ele testa os MESMOS
contratos REST que qualquer outro consumidor real usaria.
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

SERVICE_DIRS = {
    "fusion": REPO_ROOT / "epi_fusion",
    "rules": REPO_ROOT / "epi_rules",
    "incident": REPO_ROOT / "epi_incident",
    "identity": REPO_ROOT / "epi_identity",
    "vision": REPO_ROOT / "epi_ppe",
}

API_PREFIX = "/api/v1"


def _free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@dataclass
class RunningService:
    name: str
    port: int
    process: subprocess.Popen
    base_url: str
    log_path: Path

    @property
    def api_url(self) -> str:
        return f"{self.base_url}{API_PREFIX}"

    def read_log(self) -> str:
        try:
            return self.log_path.read_text()
        except OSError:
            return "(não foi possível ler o log)"

    def stop(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)


class ServiceStartupError(RuntimeError):
    pass


def _wait_healthy(base_url: str, timeout: float = 20.0) -> None:
    deadline = time.time() + timeout
    last_error: Optional[Exception] = None
    while time.time() < deadline:
        try:
            resp = httpx.get(f"{base_url}/health", timeout=1.0)
            if resp.status_code == 200:
                return
        except Exception as exc:  # noqa: BLE001 - queremos tentar de novo
            last_error = exc
        time.sleep(0.2)
    raise ServiceStartupError(f"Serviço em {base_url} não respondeu /health a tempo: {last_error}")


def start_service(name: str, env_overrides: Optional[dict] = None) -> RunningService:
    if name not in SERVICE_DIRS:
        raise ValueError(f"Serviço desconhecido: {name}")
    cwd = SERVICE_DIRS[name]
    if not cwd.exists():
        raise ServiceStartupError(f"Diretório do serviço não encontrado: {cwd}")

    port = _free_port()
    import os
    import tempfile

    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)

    if name == "identity":
        # epi_identity usa banco (SQLite) + JWT — cada instância de teste
        # precisa de um banco isolado (não reaproveitar epi_identity.db do
        # dev local) e de um segredo JWT conhecido, para o cliente de
        # integração poder mintar tokens compatíveis. environment=test evita
        # a criação de tabelas fora do fluxo já testado do próprio módulo
        # continuar funcionando (o lifespan já roda init_db fora de "production").
        fd, db_path = tempfile.mkstemp(prefix="epi_identity_it_", suffix=".db")
        os.close(fd)  # só precisamos do caminho; o SQLAlchemy abre o arquivo por conta própria
        db_file = Path(db_path)
        env.setdefault("EPI_ENVIRONMENT", "test")
        env.setdefault("EPI_DATABASE_URL", f"sqlite+aiosqlite:///{db_file}")
        env.setdefault("EPI_JWT_SECRET", "integration-tests-shared-secret-please-ignore")

    if name == "vision":
        # epi_ppe usa prefixo de env PPE_ (não EPI_ como os demais — checado
        # no próprio app/config.py do módulo). Provider mock por padrão: os
        # testes de integração não podem depender de pesos de YOLO nem de
        # hardware (câmera), conforme exigido na Fase 3.7, seção 35.
        env.setdefault("PPE_DETECTOR_PROVIDER", "mock")
        env.setdefault("PPE_ENVIRONMENT", "test")

    if env_overrides:
        env.update(env_overrides)

    # IMPORTANTE: nunca usar stdout=PIPE/stderr=PIPE sem drenar continuamente.
    # Um pipe do SO tem um buffer pequeno (tipicamente 64KB); se o processo
    # filho escrever mais que isso sem que o pai leia, o write() do filho
    # bloqueia — e como essa escrita acontece na mesma thread que roda o
    # event loop assíncrono do uvicorn, isso trava TODAS as requisições
    # seguintes, não só o log. epi_identity produz mais saída que os outros
    # serviços (avisos do PyJWT, SQLAlchemy, etc.) e foi o único afetado.
    # Solução: escrever em um arquivo temporário (sem limite de buffer) em
    # vez de um pipe.
    log_file = Path(tempfile.mkstemp(prefix=f"epi_{name}_log_", suffix=".log")[1])
    log_handle = open(log_file, "w")

    proc = subprocess.Popen(
        [
            sys.executable, "-m", "uvicorn", "app.main:app",
            "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning",
            "--loop", "asyncio",
        ],
        cwd=str(cwd),
        env=env,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )
    log_handle.close()  # o filho já herdou seu próprio fd; não precisamos mantê-lo aberto aqui
    base_url = f"http://127.0.0.1:{port}"
    try:
        _wait_healthy(base_url)
    except ServiceStartupError:
        proc.terminate()
        out = log_file.read_text() if log_file.exists() else ""
        raise ServiceStartupError(f"Falha ao subir '{name}'. Saída do processo:\n{out}")
    return RunningService(name=name, port=port, process=proc, base_url=base_url, log_path=log_file)


class Pipeline:
    """Sobe fusion + rules + incident + identity e garante o encerramento de
    todos. Uma segunda instância de identity ("identity_permissive") é
    subida com EPI_SIMILARITY_THRESHOLD=-1.0 — ver docs/contracts.md,
    "Como os estados LOW_CONFIDENCE/AMBIGUOUS são reproduzidos nos testes",
    para o porquê.

    `include_vision=True` (Fase 3.7) também sobe o epi_ppe (Módulo 2,
    detecção/tracking/associação), com o provider mock — necessário só para
    os testes do pipeline de câmera; as Fases 3.5/3.6 não o usam, por isso
    o parâmetro é opcional e desligado por padrão (evita subir um processo
    a mais sem necessidade nos testes que já existiam)."""

    def __init__(self, include_vision: bool = False) -> None:
        self.fusion: Optional[RunningService] = None
        self.rules: Optional[RunningService] = None
        self.incident: Optional[RunningService] = None
        self.identity: Optional[RunningService] = None
        self.identity_permissive: Optional[RunningService] = None
        self.vision: Optional[RunningService] = None
        self._include_vision = include_vision

    def __enter__(self) -> "Pipeline":
        self.fusion = start_service("fusion")
        self.rules = start_service("rules")
        self.incident = start_service("incident")
        self.identity = start_service("identity")
        self.identity_permissive = start_service(
            "identity", env_overrides={"EPI_SIMILARITY_THRESHOLD": "-1.0"},
        )
        if self._include_vision:
            self.vision = start_service("vision")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        services = [self.fusion, self.rules, self.incident, self.identity, self.identity_permissive]
        if self.vision is not None:
            services.append(self.vision)
        for svc in services:
            if svc is not None:
                svc.stop()
