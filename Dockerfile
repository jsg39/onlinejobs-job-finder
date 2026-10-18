# The whole app in one container: FastAPI serves the API and the built React UI on port 8000.

FROM node:22-alpine AS ui
WORKDIR /ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci
COPY ui/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY ojagent/ ojagent/
COPY profile.md ./
COPY --from=ui /ui/dist ui/dist
EXPOSE 8000
CMD ["uvicorn", "ojagent.api:app", "--host", "0.0.0.0", "--port", "8000"]
