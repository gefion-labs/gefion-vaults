import ape
from utils.constants import ROLES, WEEK, StrategyChangeType, ZERO_ADDRESS, MAX_INT
from utils.utils import days_to_secs


# STRATEGY MANAGEMENT


def test_add_strategy__no_add_strategy_manager__reverts(vault, create_strategy, bunny):
    newStrategy = create_strategy(vault)
    with ape.reverts("not allowed"):
        vault.addStrategy(newStrategy, sender=bunny)


def test_add_strategy__add_strategy_manager(vault, create_strategy, gov, bunny):
    # We temporarily give bunny the role of STRATEGY_MANAGER
    tx = vault.setRole(bunny.address, ROLES.ADD_STRATEGY_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.ADD_STRATEGY_MANAGER

    newStrategy = create_strategy(vault)
    tx = vault.addStrategy(newStrategy, sender=bunny)
    event = list(tx.decode_logs(vault.StrategyChanged))
    assert len(event) == 1
    assert event[0].strategy == newStrategy.address
    assert event[0].changeType == StrategyChangeType.ADDED


def test_revoke_strategy__no_revoke_strategy_manager__reverts(vault, strategy, bunny):
    with ape.reverts("not allowed"):
        vault.revokeStrategy(strategy, sender=bunny)


def test_revoke_strategy__revoke_strategy_manager(vault, strategy, gov, bunny):
    # We temporarily give bunny the role of STRATEGY_MANAGER
    tx = vault.setRole(bunny.address, ROLES.REVOKE_STRATEGY_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.REVOKE_STRATEGY_MANAGER

    tx = vault.revokeStrategy(strategy, sender=bunny)
    event = list(tx.decode_logs(vault.StrategyChanged))
    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].changeType == StrategyChangeType.REVOKED


def test_force_revoke_strategy__no_revoke_strategy_manager__reverts(
    vault, strategy, create_strategy, bunny
):

    with ape.reverts("not allowed"):
        vault.forceRevokeStrategy(strategy, sender=bunny)


def test_force_revoke_strategy__revoke_strategy_manager(
    vault, strategy, create_strategy, gov, bunny
):
    # We temporarily give bunny the role of STRATEGY_MANAGER
    tx = vault.setRole(bunny.address, ROLES.FORCE_REVOKE_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.FORCE_REVOKE_MANAGER

    tx = vault.forceRevokeStrategy(strategy, sender=bunny)

    event = list(tx.decode_logs(vault.StrategyChanged))
    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].changeType == StrategyChangeType.REVOKED


# ACCOUNTING MANAGEMENT


def test_set_minimumTotalIdle__no_min_idle_manager__reverts(bunny, vault):
    minimumTotalIdle = 1
    with ape.reverts("not allowed"):
        vault.setMinimumTotalIdle(minimumTotalIdle, sender=bunny)


def test_set_minimumTotalIdle__min_idle_manager(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.MINIMUM_IDLE_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.MINIMUM_IDLE_MANAGER

    assert vault.minimumTotalIdle() == 0
    minimumTotalIdle = 1
    vault.setMinimumTotalIdle(minimumTotalIdle, sender=bunny)
    assert vault.minimumTotalIdle() == 1


def test_update_maxDebt__no_maxDebt_manager__reverts(vault, strategy, bunny):
    assert vault.strategies(strategy).maxDebt == 0
    maxDebt_for_strategy = 1
    with ape.reverts("not allowed"):
        vault.updateMaxDebtForStrategy(
            strategy, maxDebt_for_strategy, sender=bunny
        )


def test_update_maxDebt__maxDebt_manager(gov, vault, strategy, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.MAX_DEBT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.MAX_DEBT_MANAGER

    assert vault.strategies(strategy).maxDebt == 0
    maxDebt_for_strategy = 1
    vault.updateMaxDebtForStrategy(strategy, maxDebt_for_strategy, sender=bunny)
    assert vault.strategies(strategy).maxDebt == 1


# Deposit and Withdraw limits


def test_set_depositLimit__no_depositLimit_manager__reverts(bunny, vault):
    depositLimit = 1
    with ape.reverts("not allowed"):
        vault.setDepositLimit(depositLimit, sender=bunny)


def test_set_depositLimit__depositLimit_manager(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.DEPOSIT_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEPOSIT_LIMIT_MANAGER

    depositLimit = 1
    assert vault.depositLimit() != depositLimit
    vault.setDepositLimit(depositLimit, sender=bunny)
    assert vault.depositLimit() == depositLimit


def test_set_depositLimit_with_limit_module__reverts(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.DEPOSIT_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEPOSIT_LIMIT_MANAGER

    depositLimit = 1

    vault.setDepositLimitModule(bunny, sender=gov)

    with ape.reverts("using module"):
        vault.setDepositLimit(depositLimit, sender=bunny)


def test_set_depositLimit_with_limit_module__override(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.DEPOSIT_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEPOSIT_LIMIT_MANAGER

    depositLimit = 1
    depositLimitModule = bunny

    vault.setDepositLimitModule(depositLimitModule, sender=gov)

    assert vault.depositLimitModule() == depositLimitModule

    with ape.reverts("using module"):
        vault.setDepositLimit(depositLimit, sender=bunny)

    tx = vault.setDepositLimit(depositLimit, True, sender=bunny)

    assert vault.depositLimit() == depositLimit
    assert vault.depositLimitModule() == ZERO_ADDRESS

    event = list(tx.decode_logs(vault.UpdateDepositLimitModule))

    assert len(event) == 1
    assert event[0].depositLimitModule == ZERO_ADDRESS

    event = list(tx.decode_logs(vault.UpdateDepositLimit))

    assert len(event) == 1
    assert event[0].depositLimit == depositLimit


def test_set_depositLimit_module__no_depositLimit_manager__reverts(bunny, vault):
    depositLimitModule = bunny
    with ape.reverts("not allowed"):
        vault.setDepositLimitModule(depositLimitModule, sender=bunny)


def test_set_depositLimit_module__depositLimit_manager(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.DEPOSIT_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEPOSIT_LIMIT_MANAGER

    depositLimitModule = bunny
    assert vault.depositLimitModule() == ZERO_ADDRESS
    tx = vault.setDepositLimitModule(depositLimitModule, sender=bunny)

    assert vault.depositLimitModule() == depositLimitModule

    event = list(tx.decode_logs(vault.UpdateDepositLimitModule))

    assert len(event) == 1
    assert event[0].depositLimitModule == depositLimitModule


def test_set_depositLimit_module_with_limit__reverts(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.DEPOSIT_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEPOSIT_LIMIT_MANAGER

    vault.setDepositLimit(1, sender=gov)

    with ape.reverts("using deposit limit"):
        vault.setDepositLimitModule(bunny, sender=gov)


def test_set_depositLimit_module_with_limit__override(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.DEPOSIT_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEPOSIT_LIMIT_MANAGER

    vault.setDepositLimit(1, sender=gov)

    depositLimitModule = bunny
    with ape.reverts("using deposit limit"):
        vault.setDepositLimitModule(depositLimitModule, sender=gov)

    tx = vault.setDepositLimitModule(depositLimitModule, True, sender=gov)

    assert vault.depositLimit() == MAX_INT
    assert vault.depositLimitModule() == depositLimitModule

    event = list(tx.decode_logs(vault.UpdateDepositLimitModule))

    assert len(event) == 1
    assert event[0].depositLimitModule == depositLimitModule

    event = list(tx.decode_logs(vault.UpdateDepositLimit))

    assert len(event) == 1
    assert event[0].depositLimit == MAX_INT


def test_set_withdraw_limit_module__no_withdraw_limit_manager__reverts(bunny, vault):
    withdrawLimitModule = bunny
    with ape.reverts("not allowed"):
        vault.setWithdrawLimitModule(withdrawLimitModule, sender=bunny)


def test_set_withdraw_limit_module__withdraw_limit_manager(gov, vault, bunny):
    # We temporarily give bunny the role
    tx = vault.setRole(bunny.address, ROLES.WITHDRAW_LIMIT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.WITHDRAW_LIMIT_MANAGER

    withdrawLimitModule = bunny
    assert vault.withdrawLimitModule() == ZERO_ADDRESS
    tx = vault.setWithdrawLimitModule(withdrawLimitModule, sender=bunny)

    assert vault.withdrawLimitModule() == withdrawLimitModule

    event = list(tx.decode_logs(vault.UpdateWithdrawLimitModule))

    assert len(event) == 1
    assert event[0].withdrawLimitModule == withdrawLimitModule


# DEBT_PURCHASER


def test_buy_debt__no_debt_purchaser__reverts(vault, strategy, bunny):
    with ape.reverts("not allowed"):
        vault.buyDebt(strategy, 0, sender=bunny)


def test_buy_debt__debt_purchaser(
    gov,
    asset,
    vault,
    bunny,
    strategy,
    fish_amount,
    add_debt_to_strategy,
    mint_and_deposit_into_vault,
):
    amount = fish_amount
    # We temporarily give bunny the role of ACCOUNTING_MANAGER

    vault.setRole(bunny.address, ROLES.DEBT_PURCHASER, sender=gov)

    mint_and_deposit_into_vault(vault, gov, amount)
    add_debt_to_strategy(gov, strategy, vault, amount)

    # Approve vault to pull funds.
    asset.mint(bunny.address, amount, sender=gov)
    asset.approve(vault.address, amount, sender=bunny)

    tx = vault.buyDebt(strategy.address, amount, sender=bunny)
    event = list(tx.decode_logs(vault.DebtPurchased))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].amount == amount

    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == amount
    assert event[0].newDebt == 0


# DEBT_MANAGER


def test_update_debt__no_debt_manager__reverts(vault, gov, strategy, bunny):
    with ape.reverts("not allowed"):
        vault.updateDebt(strategy, 10**18, sender=bunny)


def test_update_debt__debt_manager(
    gov, mint_and_deposit_into_vault, vault, strategy, bunny
):
    # We temporarily give bunny the role of DEBT_MANAGER
    tx = vault.setRole(bunny.address, ROLES.DEBT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.DEBT_MANAGER

    # Provide vault with funds
    mint_and_deposit_into_vault(vault, gov, 10**18, 10**18 // 2)

    maxDebt_for_strategy = 1
    vault.updateMaxDebtForStrategy(strategy, maxDebt_for_strategy, sender=gov)

    tx = vault.updateDebt(strategy, maxDebt_for_strategy, sender=bunny)

    event = list(tx.decode_logs(vault.DebtUpdated))
    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == 0
    assert event[0].newDebt == 1


# EMERGENCY_MANAGER


def test_shutdown_vault__no_emergency_manager__reverts(vault, bunny):
    with ape.reverts("not allowed"):
        vault.shutdownVault(sender=bunny)


def test_shutdown_vault__emergency_manager(gov, vault, bunny):
    # We temporarily give bunny the role of EMERGENCY_MANAGER
    tx = vault.setRole(bunny.address, ROLES.EMERGENCY_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.EMERGENCY_MANAGER

    assert vault.isShutdown() == False
    tx = vault.shutdownVault(sender=bunny)

    assert vault.isShutdown() == True
    event = list(tx.decode_logs(vault.Shutdown))
    assert len(event) == 1
    # lets ensure that we give the EMERGENCY_MANAGER DEBT_MANAGER permissions after shutdown
    # EMERGENCY_MANAGER=8192 DEBT_MANGER=64 -> binary or operation should give us 8256 (100001000000)
    assert vault.roles(bunny) == 8256


# REPORTING_MANAGER


def test_process_report__no_reporting_manager__reverts(vault, strategy, bunny):
    with ape.reverts("not allowed"):
        vault.processReport(strategy, sender=bunny)


def test_process_report__reporting_manager(
    gov,
    vault,
    asset,
    airdrop_asset,
    add_debt_to_strategy,
    strategy,
    bunny,
    mint_and_deposit_into_vault,
):
    # We temporarily give bunny the role of ACCOUNTING_MANAGER
    tx = vault.setRole(bunny.address, ROLES.REPORTING_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.REPORTING_MANAGER

    # Provide liquidity into vault
    mint_and_deposit_into_vault(vault, gov, 10**18, 10**18 // 2)
    # add debt to strategy
    add_debt_to_strategy(gov, strategy, vault, 2)
    # airdrop gain to strategy
    airdrop_asset(gov, asset, strategy, 1)
    strategy.report(sender=gov)

    tx = vault.processReport(strategy.address, sender=bunny)

    event = list(tx.decode_logs(vault.StrategyReported))
    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == 1
    assert event[0].loss == 0


# SET_ACCOUNTANT_MANAGER


def test_set_accountant__no_accountant_manager__reverts(bunny, vault):
    with ape.reverts("not allowed"):
        vault.setAccountant(bunny, sender=bunny)


def test_set_accountant__accountant_manager(gov, vault, bunny):
    # We temporarily give bunny the role of DEBT_MANAGER
    tx = vault.setRole(bunny.address, ROLES.ACCOUNTANT_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.ACCOUNTANT_MANAGER

    assert vault.accountant() != bunny
    vault.setAccountant(bunny, sender=bunny)
    assert vault.accountant() == bunny


# QUEUE MANAGER


def test_set_default_queue__no_queue_manager__reverts(bunny, vault):
    with ape.reverts("not allowed"):
        vault.setDefaultQueue([], sender=bunny)


def test_useDefaultQueue__no_queue_manager__reverts(bunny, vault):
    with ape.reverts("not allowed"):
        vault.setUseDefaultQueue(True, sender=bunny)


def test_set_default_queue__queue_manager(gov, vault, strategy, bunny):
    # We temporarily give bunny the role of DEBT_MANAGER
    tx = vault.setRole(bunny.address, ROLES.QUEUE_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.QUEUE_MANAGER

    assert vault.getDefaultQueue() != []
    vault.setDefaultQueue([], sender=bunny)
    assert vault.getDefaultQueue() == []


def test_set_useDefaultQueue__queue_manager(gov, vault, strategy, bunny):
    # We temporarily give bunny the role of DEBT_MANAGER
    tx = vault.setRole(bunny.address, ROLES.QUEUE_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.QUEUE_MANAGER

    assert vault.useDefaultQueue() == False
    tx = vault.setUseDefaultQueue(True, sender=bunny)

    event = list(tx.decode_logs(vault.UpdateUseDefaultQueue))
    assert len(event) == 1
    assert event[0].useDefaultQueue == True
    assert vault.useDefaultQueue() == True


# PROFIT UNLOCK MANAGER


def test_set_profit_unlock__no_profit_unlock_manager__reverts(bunny, vault):
    with ape.reverts("not allowed"):
        vault.setProfitMaxUnlockTime(WEEK // 2, sender=bunny)


def test_set_profit_unlock__profit_unlock_manager(gov, vault, bunny):
    # We temporarily give bunny the role of profit unlock manager
    tx = vault.setRole(bunny.address, ROLES.PROFIT_UNLOCK_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.PROFIT_UNLOCK_MANAGER

    time = WEEK // 2
    assert vault.profitMaxUnlockTime() != time
    vault.setProfitMaxUnlockTime(time, sender=bunny)
    assert vault.profitMaxUnlockTime() == time


def test_set_profit_unlock__to_high__reverts(gov, vault, bunny):
    # We temporarily give bunny the role of profit unlock manager
    tx = vault.setRole(bunny.address, ROLES.PROFIT_UNLOCK_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.PROFIT_UNLOCK_MANAGER

    time = int(1e20)
    current_time = vault.profitMaxUnlockTime()

    with ape.reverts("profit unlock time too long"):
        vault.setProfitMaxUnlockTime(time, sender=bunny)

    assert vault.profitMaxUnlockTime() == current_time


def test__add_role(gov, vault, bunny):
    assert vault.roles(bunny) == 0

    tx = vault.addRole(bunny.address, ROLES.PROFIT_UNLOCK_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.PROFIT_UNLOCK_MANAGER

    assert vault.roles(bunny) == ROLES.PROFIT_UNLOCK_MANAGER

    tx = vault.addRole(bunny.address, ROLES.FORCE_REVOKE_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.PROFIT_UNLOCK_MANAGER | ROLES.FORCE_REVOKE_MANAGER

    assert (
        vault.roles(bunny) == ROLES.PROFIT_UNLOCK_MANAGER | ROLES.FORCE_REVOKE_MANAGER
    )

    tx = vault.addRole(bunny.address, ROLES.REPORTING_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert (
        event[0].role
        == ROLES.PROFIT_UNLOCK_MANAGER
        | ROLES.FORCE_REVOKE_MANAGER
        | ROLES.REPORTING_MANAGER
    )

    assert (
        vault.roles(bunny)
        == ROLES.PROFIT_UNLOCK_MANAGER
        | ROLES.FORCE_REVOKE_MANAGER
        | ROLES.REPORTING_MANAGER
    )


def test__remove_role(gov, vault, bunny):
    assert vault.roles(bunny) == 0

    tx = vault.setRole(
        bunny.address,
        ROLES.PROFIT_UNLOCK_MANAGER
        | ROLES.FORCE_REVOKE_MANAGER
        | ROLES.REPORTING_MANAGER,
        sender=gov,
    )

    assert (
        vault.roles(bunny)
        == ROLES.PROFIT_UNLOCK_MANAGER
        | ROLES.FORCE_REVOKE_MANAGER
        | ROLES.REPORTING_MANAGER
    )

    tx = vault.removeRole(bunny.address, ROLES.FORCE_REVOKE_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.PROFIT_UNLOCK_MANAGER | ROLES.REPORTING_MANAGER

    assert vault.roles(bunny) == ROLES.PROFIT_UNLOCK_MANAGER | ROLES.REPORTING_MANAGER

    tx = vault.removeRole(bunny.address, ROLES.REPORTING_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == ROLES.PROFIT_UNLOCK_MANAGER

    assert vault.roles(bunny) == ROLES.PROFIT_UNLOCK_MANAGER

    tx = vault.removeRole(bunny.address, ROLES.PROFIT_UNLOCK_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == 0

    assert vault.roles(bunny) == 0


def test__add_role__wont_remove(gov, vault):
    roles = ROLES(vault.roles(gov))
    role = ROLES.MINIMUM_IDLE_MANAGER

    assert role in roles

    tx = vault.addRole(gov.address, role, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == gov.address
    assert event[0].role == roles

    assert roles == vault.roles(gov)
    assert role in ROLES(vault.roles(gov))

    # Make sure we can set min idle.
    vault.setMinimumTotalIdle(100, sender=gov)

    assert vault.minimumTotalIdle() == 100


def test__remove_role__wont_add(gov, vault, bunny, strategy):
    assert vault.roles(bunny) == 0

    tx = vault.removeRole(bunny.address, ROLES.ADD_STRATEGY_MANAGER, sender=gov)

    event = list(tx.decode_logs(vault.RoleSet))
    assert len(event) == 1
    assert event[0].account == bunny.address
    assert event[0].role == 0

    assert vault.roles(bunny) == 0

    with ape.reverts("not allowed"):
        vault.addStrategy(strategy, sender=bunny)
