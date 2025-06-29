from dataclasses import dataclass
from environs import Env


@dataclass
class TCSClient:
    token: str
    id: str
    sandbox_token: str


@dataclass
class Config:
    tcs_client: TCSClient


def load_config(path: str = None) -> Config:
    env: Env = Env()
    env.read_env(path)

    client = TCSClient(
        token=env('TINKOFF_TOKEN'), 
        id=env('TINKOFF_ACCOUNT'), 
        sandbox_token=env('SANDBOX_TOKEN')
    )
    return Config(tcs_client=client)
                                    