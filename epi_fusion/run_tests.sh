#!/usr/bin/env bash
# Roda os testes da Fase 3.1 (epi_fusion) isolados, num venv próprio.
# Uso: a partir da pasta epi_vision_projeto_completo/
#   bash epi_fusion/run_tests.sh

set -euo pipefail
cd "$(dirname "$0")"

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip -q
pip install -e ".[dev]" -q

echo ""
echo "=== Testes unitários ==="
pytest tests/unit -v

echo ""
echo "=== Testes de integração (do próprio módulo, TestClient em processo único) ==="
pytest tests/integration -v

echo ""
echo "=== Suíte completa com resumo ==="
pytest tests -q
