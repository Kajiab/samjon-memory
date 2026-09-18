# Portal Security

**Document ID:** SAMJON-PS-001
**Status:** CANONICAL
**Owner:** Samjon Memory Engineering

## 1. Purpose

Portal security for Samjon Memory Core V1.

## 2. Security

- X-Service-Token header for read access
- X-Admin-Token header for write access
- CSRF protection via SameSite cookies
- Token validation before portal access
