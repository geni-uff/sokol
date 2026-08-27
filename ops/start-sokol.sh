#!/usr/bin/env bash
# SOKOL — sobe a stack (Linux nativo ou Ubuntu no WSL2).
# Autor: Matheus C. Pestana
set -u

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo
echo "  SOKOL — a subir os containers"
echo

if ! command -v docker >/dev/null 2>&1; then
  echo "ERRO: docker nao esta no PATH."
  echo "No Windows: instale o Docker Engine DENTRO do Ubuntu (WSL2), nao o Docker Desktop."
  echo "Passos: INSTRUCOES.md, secao 6.0."
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "ERRO: o daemon Docker nao responde."
  echo "Tente: sudo service docker start"
  exit 1
fi

if [[ ! -f .env ]]; then
  cp deploy/env.example .env
  echo "Aviso: criei .env a partir de deploy/env.example. Defina POSTGRES_PASSWORD."
fi

mkdir -p data/media-cache data/staging data/backups UFDRsTest

if command -v lms >/dev/null 2>&1; then
  echo "A ligar o servidor LM Studio (lms)..."
  lms server start >/dev/null 2>&1 || true
fi

echo "A subir os containers. A primeira vez pode demorar varios minutos."
(
  cd deploy
  docker compose --env-file ../.env up --build -d
)

echo "A esperar http://localhost:8000/health ..."
ok=0
for _ in $(seq 1 60); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 3
done
if [[ "$ok" -ne 1 ]]; then
  echo "ERRO: a API nao respondeu. Veja: docker logs sokol-api"
  exit 1
fi

echo "A aplicar migracoes..."
docker exec sokol-api alembic upgrade head

echo
echo "SOKOL no ar: http://localhost:3000"
echo "Login de desenvolvimento: admin / admin123"
echo "No Windows, abra esse endereco no navegador do Windows."
echo

if command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://localhost:3000 >/dev/null 2>&1 || true
fi
