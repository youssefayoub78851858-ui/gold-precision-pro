FROM node:24-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ /app/app/
COPY service/ /app/service/
COPY broker.py broker_process.py supervise.py startup_guard.py handoff_guard.py process_inventory.py timing.js timing-cli.js historical.js handoff-manifest.json entrypoint.py usage_probe.py acceptance_watch.py v3_market_structure.js v3_multitimeframe.js v3_trade_plan.js /app/
COPY eodhd_ws_bridge.js eodhd_private_readiness.py /app/
ENV DATA_DIR=/var/data/gold-live PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM
CMD ["python3", "/app/entrypoint.py"]
