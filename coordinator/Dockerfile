FROM node:24-bookworm-slim@sha256:01d566e8d94d8c619591d78652babfccd3c6992a3dffa9ed5ab39e11cf6c70e9
RUN apt-get update && apt-get install -y --no-install-recommends python3 ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/ /app/app/
COPY service/ /app/service/
COPY broker.py broker_process.py supervise.py startup_guard.py handoff_guard.py process_inventory.py timing.js timing-cli.js historical.js handoff-manifest.json entrypoint.py usage_probe.py acceptance_watch.py v3_market_structure.js v3_multitimeframe.js v3_trade_plan.js /app/
COPY eodhd_ws_bridge.js eodhd_private_readiness.py eodhd_review_monitor.py eodhd_research_bridge.py xauusd_feed_gate.py xauusd_research_pipeline.py research_monitor.py research_notification.py private_review_watchdog.py private_feed_recovery.py private_eodhd_worker.py paper_admission_gate.py paper_cost_preflight.py private_mobile_dashboard.html fxcm_mobile_readiness.py /app/
# Public BiQuote 24-hour review: no trading stack, keys, or paid-provider calls.
COPY biquote_offline_source_audit.py biquote_overlap_evidence.py biquote_session_gap_audit.py biquote_quote_mid_parity.py biquote_sampled_spread_buckets.py biquote_quote_cadence.py biquote_public_one_shot.py biquote_24h_observer.py biquote_seven_day_review.py biquote_private_forward_vault.py biquote_forward_shadow_review.py biquote_24h_final_verdict.py private_forward_capacity_preflight.py ultimate_batch_acceptance.py /app/
# Offline-only owner-operated backup and restore tools for a FUTURE image.
# Merely baking these files makes no backup and does not run them or authorize redeploy.
COPY biquote_collector_backup_preflight.py biquote_collector_restore_rehearsal.py biquote_private_archive_predeploy_guard.py biquote_owner_private_copy_once.py biquote_owner_vault_inventory.py /app/
# Frozen research modules: Node runs offline against owner-only forward vault.
# They are not connected to MT5, order endpoints or the public demo.
COPY v3_ultimate.js ultimate_four_stage_review.js independent_context_timing_preflight.js biquote_session_h4_continuity_audit.js biquote_vendor_declared_session.js ultimate_signal_quality.js ultimate_signal_quality_report.js ultimate_entry_robustness.js ultimate_shadow_admission.js /app/
ENV DATA_DIR=/var/data/gold-live PYTHONUNBUFFERED=1
STOPSIGNAL SIGTERM
CMD ["python3", "/app/entrypoint.py"]
