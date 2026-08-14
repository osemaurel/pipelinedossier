# Image unique : l'interface est compilée puis servie par le serveur Python.
# Une seule adresse à exposer, donc un seul service à héberger.

FROM node:22-alpine AS interface
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
COPY palabdossiercollecte.xlsx ./
COPY --from=interface /app/frontend/dist frontend/dist

RUN mkdir -p uploads outputs temp

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
