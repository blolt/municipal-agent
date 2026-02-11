-- Migration 003: Setup pgvector Extension
-- Enables semantic search capabilities (for future use)

CREATE EXTENSION IF NOT EXISTS vector;

-- Note: Vector embeddings will be added in a future migration
-- This migration simply ensures the extension is available
