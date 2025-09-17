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
    return Config(tcs_client=client)
                                    