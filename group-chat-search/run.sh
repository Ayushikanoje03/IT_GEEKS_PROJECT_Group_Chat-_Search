#!/usr/bin/env bash
set -euo pipefail

uvicorn backend.main:app --app-dir . --reload
