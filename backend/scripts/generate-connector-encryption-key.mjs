#!/usr/bin/env node
/**
 * Generate CONNECTOR_SECRETS_ENCRYPTION_KEY (32 bytes → 64 hex chars).
 *
 * Usage: node backend/scripts/generate-connector-encryption-key.mjs
 */
import crypto from "node:crypto";

const encryptionKey = crypto.randomBytes(32).toString("hex");

if (!/^[a-fA-F0-9]{64}$/.test(encryptionKey)) {
  console.error("Generated key failed validation");
  process.exit(1);
}

console.log(`CONNECTOR_SECRETS_ENCRYPTION_KEY=${encryptionKey}`);
