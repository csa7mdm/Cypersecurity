# Test configuration for Brain service
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

# Test settings
TEST_DATABASE_URL = "postgresql://test_user:test_pass@localhost:5432/test_cyper_security"
TEST_REDIS_URL = "redis://localhost:6379/1"

# Mock API keys for testing
os.environ.setdefault("OPENROUTER_API_KEY", "test_key_123")
os.environ.setdefault("AI_MODEL", "test_model")
