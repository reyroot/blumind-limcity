# Limcity — Future Implementation

> Planned work not yet built. For what exists today, see `history.md`.

## Image storage for waste reports

**Status:** Not implemented (MVP discards images after classification).

**Current behavior:** When a citizen sends a photo via WhatsApp or Telegram, the pipeline downloads the image bytes in memory, passes them to the classifier, and does not persist the file. The `waste_reports.image_url` column exists but is always `null`.

**Why add it later:**

- Audit trail and dispute resolution (verify what was reported)
- Re-classification when the AI model improves (YOLOv8 or better Gemini prompts)
- LGPD compliance: explicit retention policy, consent, and deletion workflows

**Suggested approach:**

1. **Storage backend** — start with local disk (`app/storage/reports/`) or S3-compatible object storage; abstract behind a small `ImageStore` service (similar to the classifier Strategy pattern).
2. **Persist on report creation** — after `download_image()`, upload bytes, set `image_url` on `WasteReport` before classification.
3. **Filename convention** — e.g. `{report_id}.jpg` or `{channel}/{message_id}.jpg`; store content-type from the channel response.
4. **API exposure** — optional signed URL or authenticated `GET /api/reports/{id}/image` for dashboard/operators (not public hotlinking).
5. **Retention** — configurable TTL in settings (e.g. delete images after N days unless flagged); document in privacy policy.

**Schema:** No migration required for URL-only storage; `image_url` is already nullable on `waste_reports`. Add columns later only if needed (e.g. `image_mime_type`, `image_size_bytes`, `image_deleted_at`).

**Channels:** Wire once in `report_conversation._complete_report()` so WhatsApp and Telegram both benefit without duplicating logic.
