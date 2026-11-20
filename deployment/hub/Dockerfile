FROM us-east1-docker.pkg.dev/think-tank-solutions-ai/cloud-run-source-deploy/think-tank-hub@sha256:65d0ff67e83e691a80ae9ff004a9b1f15a7b2f8837375e74a0a4a37e436eba05
USER root
RUN apk add --no-cache python3
WORKDIR /app
COPY --chown=node:node deployment/hub/server.mjs deployment/hub/simutrade-proxy.mjs deployment/hub/launch.mjs ./
COPY --chown=node:node production.py server.py ./simutrade/
USER node
ENV NODE_ENV=production
EXPOSE 8080
CMD ["node", "launch.mjs"]
