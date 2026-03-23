FROM ghcr.io/astral-sh/uv:python3.12-alpine

RUN mkdir /code
WORKDIR /code

# copy just the pyproject and uv.lock files and install before rest of code to avoid having to
# reinstall packages during build every time code changes
COPY pyproject.toml uv.lock ./
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache \
    uv sync --locked --no-dev

ENV PATH="/code/.venv/bin:$PATH"

CMD ["nogisync", "--help"]