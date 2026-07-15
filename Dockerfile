# Dockerfile
#
# Builds a Lambda container image containing your existing ClinIQ code
# (agent.py, tools.py, schema_metadata.py — unchanged) plus lambda_handler.py
# and a bundled copy of data/mimic.db.
#
# AWS provides official Python base images preconfigured for the Lambda runtime
# — this is the recommended starting point per AWS's own docs.

FROM public.ecr.aws/lambda/python:3.12

# Install Python dependencies first (separate layer so Docker caches this step
# and doesn't reinstall every time you only change agent.py/tools.py)
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r requirements.txt
# 2. Tell HuggingFace to use /tmp at runtime (writable)
ENV HF_HOME=/tmp
ENV SENTENCE_TRANSFORMERS_HOME=/tmp/sentence_transformers
# 1. Pre-download the model at build time into /opt/ml/model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2', cache_folder='/opt/ml/model')"



# Copy existing, unmodified application code
COPY schema_metadata.py ${LAMBDA_TASK_ROOT}/
COPY tools.py ${LAMBDA_TASK_ROOT}/
COPY db_query_agent.py ${LAMBDA_TASK_ROOT}/
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Bundle the SQLite database directly into the image (confirmed <200MB, fits
# comfortably under the 10GB container image limit)
COPY data/mimic.db ${LAMBDA_TASK_ROOT}/data/

# Lambda needs to know which function in which file is the entry point.
# Format: <filename_without_.py>.<function_name>
CMD ["lambda_handler.handler"]
