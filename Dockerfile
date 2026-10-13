# Dockerfile
#
# Builds a Lambda container image containing your existing ClinIQ code
# (agent.py, tools.py, schema_metadata.py — unchanged) plus lambda_handler.py
# and a bundled copy of data/mimic.db.
#
# AWS provides official Python base images preconfigured for the Lambda runtime
# — this is the recommended starting point per AWS's own docs.

FROM python:3.12-slim
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"
WORKDIR /app
# Install Python dependencies first (separate layer so Docker caches this step
# and doesn't reinstall every time you only change agent.py/tools.py)
COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt
COPY --chown=user . .
EXPOSE 8080
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]