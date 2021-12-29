FROM python:3.10

RUN curl -sSL https://install.python-poetry.org | python3 -


WORKDIR /gmail-cleaner

COPY . .

RUN /root/.local/bin/poetry install


EXPOSE 8080

CMD /root/.local/bin/poetry run python gmail_cleaner/main.py

# CMD /root/.local/bin/poetry run python -m http.server 8080 
