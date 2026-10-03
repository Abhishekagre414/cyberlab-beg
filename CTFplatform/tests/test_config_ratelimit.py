import pytest

import config


def _prod(monkeypatch, uri, serverless=False):
    monkeypatch.setattr(config.ProductionConfig, 'RATELIMIT_STORAGE_URI', uri)
    monkeypatch.setattr(config, 'IS_SERVERLESS', serverless)
    monkeypatch.delenv('ALLOW_MEMORY_RATELIMIT', raising=False)


def test_production_refuses_memory_rate_limits(monkeypatch):
    _prod(monkeypatch, 'memory://')
    with pytest.raises(RuntimeError, match='REDIS_URL'):
        config._enforce_production_requirements(config.ProductionConfig)


def test_production_accepts_redis(monkeypatch):
    _prod(monkeypatch, 'redis://redis:6379/0')
    config._enforce_production_requirements(config.ProductionConfig)


def test_explicit_single_worker_override(monkeypatch):
    _prod(monkeypatch, 'memory://')
    monkeypatch.setenv('ALLOW_MEMORY_RATELIMIT', 'true')
    config._enforce_production_requirements(config.ProductionConfig)


def test_serverless_and_development_are_exempt(monkeypatch):
    _prod(monkeypatch, 'memory://', serverless=True)
    config._enforce_production_requirements(config.ProductionConfig)
    _prod(monkeypatch, 'memory://')
    config._enforce_production_requirements(config.DevelopmentConfig)
