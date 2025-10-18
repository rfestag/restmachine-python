"""
Tests for hierarchical configuration system.
"""

import os
import tempfile
from pathlib import Path
import pytest
from omegaconf import OmegaConf
from restmachine.config import HierarchicalSettings


@pytest.fixture
def config_dir():
    """Create a temporary config directory with test configs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir)

        # Create hierarchy.yaml
        hierarchy = {
            'default_path': 'local',
            'default_environment': 'development'
        }
        (config_path / 'hierarchy.yaml').write_text(OmegaConf.to_yaml(hierarchy))

        # Create local/development.yaml (complete config)
        (config_path / 'local').mkdir()
        dev_config = {
            'app': {
                'name': 'testapp',
                'debug': True,
                'log_level': 'DEBUG'
            },
            'database': {
                'backend': 'memory'
            }
        }
        (config_path / 'local' / 'development.yaml').write_text(OmegaConf.to_yaml(dev_config))

        # Create local/production.yaml (complete config)
        prod_config = {
            'app': {
                'name': 'testapp',
                'debug': False,
                'log_level': 'WARNING'
            },
            'database': {
                'backend': 'dynamodb'
            }
        }
        (config_path / 'local' / 'production.yaml').write_text(OmegaConf.to_yaml(prod_config))

        yield config_path


def test_default_config_loading(config_dir):
    """Test loading default configuration (no env vars)."""
    # Clear environment variables
    os.environ.pop('RESTMACHINE_CONFIG_PATH', None)
    os.environ.pop('RESTMACHINE_ENVIRONMENT', None)

    settings = HierarchicalSettings(config_dir=config_dir)

    # Should load local/development.yaml (from hierarchy defaults)
    assert settings.get('app.name') == 'testapp'
    assert settings.get('app.debug') is True
    assert settings.get('app.log_level') == 'DEBUG'
    assert settings.get('database.backend') == 'memory'


def test_environment_override(config_dir, monkeypatch):
    """Test environment-specific configuration."""
    monkeypatch.setenv('RESTMACHINE_CONFIG_PATH', 'local')
    monkeypatch.setenv('RESTMACHINE_ENVIRONMENT', 'production')

    settings = HierarchicalSettings(config_dir=config_dir)

    # Should load local/production.yaml
    assert settings.get('app.name') == 'testapp'
    assert settings.get('app.debug') is False
    assert settings.get('app.log_level') == 'WARNING'
    assert settings.get('database.backend') == 'dynamodb'


def test_attribute_access(config_dir):
    """Test accessing config values as attributes."""
    settings = HierarchicalSettings(config_dir=config_dir)

    # Dot notation access
    assert settings.app.name == 'testapp'
    assert settings.database.backend == 'memory'


def test_get_with_default(config_dir):
    """Test get() method with default values."""
    settings = HierarchicalSettings(config_dir=config_dir)

    # Existing key
    assert settings.get('app.name') == 'testapp'

    # Non-existent key with default
    assert settings.get('nonexistent.key', 'default_value') == 'default_value'


def test_hierarchical_path_loading(config_dir):
    """Test loading configs from nested hierarchy."""
    # Create aws/123456789012/us-east-1/production.yaml
    aws_path = config_dir / 'aws' / '123456789012' / 'us-east-1'
    aws_path.mkdir(parents=True)

    # AWS partition config
    aws_config = {'aws': {'partition': 'aws'}}
    (config_dir / 'aws' / 'config.yaml').write_text(OmegaConf.to_yaml(aws_config))

    # Account config
    account_config = {'aws': {'account_id': '123456789012'}}
    (config_dir / 'aws' / '123456789012' / 'config.yaml').write_text(
        OmegaConf.to_yaml(account_config)
    )

    # Region production config (complete)
    prod_config = {
        'app': {
            'name': 'testapp',
            'log_level': 'ERROR'
        },
        'aws': {'region': 'us-east-1'}
    }
    (aws_path / 'production.yaml').write_text(OmegaConf.to_yaml(prod_config))

    os.environ['RESTMACHINE_CONFIG_PATH'] = 'aws/123456789012/us-east-1'
    os.environ['RESTMACHINE_ENVIRONMENT'] = 'production'

    settings = HierarchicalSettings(config_dir=config_dir)

    # Should merge all levels
    assert settings.get('app.name') == 'testapp'  # From production.yaml
    assert settings.get('app.log_level') == 'ERROR'  # From production.yaml
    assert settings.get('aws.partition') == 'aws'  # From aws/config.yaml
    assert settings.get('aws.account_id') == '123456789012'  # From account config
    assert settings.get('aws.region') == 'us-east-1'  # From region production


def test_omegaconf_interpolation(config_dir):
    """Test OmegaConf variable interpolation."""
    # Create config with interpolation
    interp_config = {
        'base_url': 'https://example.com',
        'api_url': '${base_url}/api',
        'env_var': '${oc.env:TEST_VAR,default_value}'
    }
    (config_dir / 'local' / 'development.yaml').write_text(OmegaConf.to_yaml(interp_config))

    os.environ['TEST_VAR'] = 'from_environment'
    os.environ.pop('RESTMACHINE_CONFIG_PATH', None)
    os.environ.pop('RESTMACHINE_ENVIRONMENT', None)

    settings = HierarchicalSettings(config_dir=config_dir)

    # Should resolve interpolations
    assert settings.get('base_url') == 'https://example.com'
    assert settings.get('api_url') == 'https://example.com/api'
    assert settings.get('env_var') == 'from_environment'

    # Test default value when env var not set
    os.environ.pop('TEST_VAR', None)
    settings = HierarchicalSettings(config_dir=config_dir)
    assert settings.get('env_var') == 'default_value'


def test_missing_attribute_returns_none(config_dir):
    """Test that accessing non-existent attribute returns None."""
    settings = HierarchicalSettings(config_dir=config_dir)

    # Non-existent keys return None (OmegaConf behavior)
    assert settings.get('nonexistent.key') is None
