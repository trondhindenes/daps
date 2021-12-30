FROM python:3.9 AS parent
WORKDIR /app
RUN pip install pipenv
COPY Pipfile /app/
COPY Pipfile.lock /app/
ENV PYTHONUNBUFFERED=1


FROM parent AS base
RUN pipenv install --deploy --system


FROM base as Prod
COPY daps /app
ENTRYPOINT ["gunicorn"]
CMD ["app:app"]
