"""Global configuration and paths."""

from pathlib import Path
from platformdirs import user_config_dir, user_data_dir, user_cache_dir, user_state_dir


class GlobalPaths:
    """Global application paths."""
    
    def __init__(self):
        self.app_name = "opencode"
        
        self.data = Path(user_data_dir(self.app_name))
        self.cache = Path(user_cache_dir(self.app_name))
        self.config = Path(user_config_dir(self.app_name))
        self.state = Path(user_state_dir(self.app_name))
        
        self.bin = self.data / "bin"
        self.providers = self.config / "providers"
        
        # Ensure directories exist
        for path in [self.data, self.cache, self.config, self.state, self.bin, self.providers]:
            path.mkdir(parents=True, exist_ok=True)


# Global instance
Path = GlobalPaths()