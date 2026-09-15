# The default is the reviewed Python 3.11 base pinned in image.env.  Callers may
# replace it only with another explicitly reviewed immutable digest.
ARG PYTHON_IMAGE=python@sha256:528257d48c1da0dcecc2e725d1ae34498d60c965f1241e39cd6a85a8859bdf84
FROM ${PYTHON_IMAGE}
WORKDIR /app
COPY src/forex /app/src/forex
COPY scripts/run_bls_n8n_service.py /app/scripts/run_bls_n8n_service.py
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 65532:65532
CMD ["python3", "/app/scripts/run_bls_n8n_service.py"]
