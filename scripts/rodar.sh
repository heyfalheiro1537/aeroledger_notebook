#!/bin/sh
# Roda o notebook do começo ao fim, sem interface, gravando as saídas nele.
# Precisa de um PostgreSQL em localhost:54329 (scripts/pg_local.sh ou docker compose up -d).
set -e
cd "$(dirname "$0")/.."
jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1200 experimentos.ipynb
echo "experimentos.ipynb executado"
