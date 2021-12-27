FROM python:3.10

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /gmail-cleaner

RUN /root/.local/bin/poetry install

CMD ["poetry", "shell"]
