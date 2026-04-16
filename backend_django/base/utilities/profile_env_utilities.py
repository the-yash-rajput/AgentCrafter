import os


def get_environment() -> str:
    """
    Returns the environment name based on configuration.
    """
    profile_env = os.getenv("PROFILE_ENV", "local").strip().lower() or "local"

    if profile_env == "prod":
        return "production"
    if profile_env == "stage":
        return os.getenv("ENV_NAMESPACE", "cellular").strip().lower() or "cellular"
    return "local"

