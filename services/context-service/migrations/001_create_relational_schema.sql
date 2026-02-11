-- Migration 001: Create Relational Schema
-- Creates the core tables for events and runs
-- Note: The checkpoints table is managed by LangGraph's AsyncPostgresSaver

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Events table: Immutable log of all ingress and egress signals
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_id UUID NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    source VARCHAR(100) NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_events_correlation_id ON events(correlation_id);
CREATE INDEX idx_events_event_type ON events(event_type);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_created_at ON events(created_at);

-- Runs table: Tracks agent execution sessions
CREATE TABLE IF NOT EXISTS runs (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    correlation_id UUID NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'completed', 'failed', 'waiting')),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_runs_correlation_id ON runs(correlation_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status);
