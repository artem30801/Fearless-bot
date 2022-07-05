from dynaconf import Dynaconf, Validator


def load_settings():
    settings = Dynaconf(
        settings_files=["config/config.json", "config/.secrets.json"],
        environments=True,
        load_dotenv=True,
    )

    settings.validators.register(Validator("DISCORD_TOKEN", "DATABASE_ADDRESS", must_exist=True))
    settings.validators.validate()

    return settings
