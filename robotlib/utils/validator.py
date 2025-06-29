from robotlib.factories.robot import AsyncInvestClient
from tinkoff.invest import AccountType, AccountStatus, AccessLevel, InvestError
from robotlib.utils.lazy import lazy_property
from robotlib.factories.logger import LoggerFactory

class AccountValidator:
    @lazy_property
    def logger(self):
        return LoggerFactory.create_logger(__name__)
    
    def is_account_valid(self, account_id: str, token: str):
        try:
            with AsyncInvestClient(account_id=account_id, token=token) as client:
                account = [acc for acc in client.users.get_accounts().accounts if acc.id == account_id][0]

                if account.type not in [AccountType.ACCOUNT_TYPE_TINKOFF, AccountType.ACCOUNT_TYPE_INVEST_BOX]:
                    self.logger.error(f'Account type {account.type} is not supported', exc_info=True)
                    raise ValueError('Unsupported account type')

                if account.status != AccountStatus.ACCOUNT_STATUS_OPEN:
                    self.logger.error(f'Account status {account.status} is not supported', exc_info=True)
                    raise ValueError('Unsupported account status')

                if account.access_level != AccessLevel.ACCOUNT_ACCESS_LEVEL_FULL_ACCESS:
                    self.logger.error(f'No access to account. Current level is {account.access_level}', exc_info=True)
                    raise ValueError('Insufficient access level')

                return True
            
        except InvestError as error:
            self.logger.error(f'Failed to validate account. Exception: {error}', exc_info=True)
            raise error

