# Troubleshooting

**Document ID:** SAMJON-TS-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Troubleshooting guide for Samjon Memory Core V1.

## 2. Common Issues

- Migration required: run migrations (schema 1.1.0)
- Database unavailable: check file permissions
- Version conflict: check expected_version
- Idempotency conflict: use different key
- Sensitive data rejected: check input for credentials
- Purge rejected: check the 30-day retention window, `PURGE` confirmation, and admin actor
- Restore rejected: the record is purged (purged records cannot be restored)
