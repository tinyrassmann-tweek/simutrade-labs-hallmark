FROM python:3.12-slim
WORKDIR /app
COPY server.py ./
COPY production.py ./
COPY public ./public
RUN useradd --uid 10001 --create-home app && mkdir data && chown app:app data
USER app
ENV PORT=8080
EXPOSE 8080
CMD ["python", "production.py"]
