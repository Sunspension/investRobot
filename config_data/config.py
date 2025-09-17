from dataclasses import dataclass
from environs import Env


@dataclass
class TCSClient:
    token: str
    account_id: str
    sandbox_token: str
    # Лимиты запросов (могут быть переопределены из .env)
    rate_limit_get_rps: float = 8.0
    rate_limit_get_burst: int = 16
    rate_limit_post_rps: float = 2.0
    rate_limit_post_burst: int = 4


@dataclass
class Config:
    tcs_client: TCSClient
    clearing_day_start: str
    clearing_day_end: str
    clearing_evening_start: str
    clearing_evening_end: str


def load_config(path: str = None) -> Config:
    env: Env = Env()
    env.read_env(path)

    client = TCSClient(
        token=env('TINKOFF_TOKEN'), 
        account_id=env('TINKOFF_ACCOUNT'), 
        sandbox_token=env('SANDBOX_TOKEN'),
        rate_limit_get_rps=float(env('TCS_RATE_GET_RPS', 8.0)),
        rate_limit_get_burst=int(env('TCS_RATE_GET_BURST', 16)),
        rate_limit_post_rps=float(env('TCS_RATE_POST_RPS', 2.0)),
        rate_limit_post_burst=int(env('TCS_RATE_POST_BURST', 4)),
    )
    # Clearing windows (HH:MM) — configurable
    clearing_day_start = env('CLEARING_DAY_START', '14:00')
    clearing_day_end = env('CLEARING_DAY_END', '14:05')
    clearing_evening_start = env('CLEARING_EVENING_START', '18:50')
    clearing_evening_end = env('CLEARING_EVENING_END', '19:05')

    return Config(
        tcs_client=client,
        clearing_day_start=clearing_day_start,
        clearing_day_end=clearing_day_end,
        clearing_evening_start=clearing_evening_start,
        clearing_evening_end=clearing_evening_end,
    )
                                    