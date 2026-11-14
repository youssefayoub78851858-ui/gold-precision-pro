FROM node:24-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ /app/app/
COPY service/ /app/service/
COPY broker.py broker_process.py supervise.py startup_guard.py handoff_guard.py process_inventory.py timing.js timing-cli.js historical.js handoff-manifest.json entrypoint.py usage_probe.py acceptance_watch.py v3_market_structure.js v3_multitimeframe.js v3_trade_plan.js /app/
COPY eodhd_ws_bridge.js eodhd_private_readiness.py eodhd_review_monitor.py eodhd_research_bridge.py xauusd_feed_gate.py xauusd_research_pipeline.py research_monitor.py research_notification.py private_review_watchdog.py private_feed_recovery.py private_eodhd_worker.py paper_admission_gate.py paper_cost_preflight.py private_mobile_dashboard.html fxcm_mobile_readiness.py /app/
ENV DATA_DIR=/var/data/gold-live PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM
CMD ["python3", "/app/entrypoint.py"]
