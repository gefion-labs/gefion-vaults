import ape
import pytest
from ape import chain
from utils import checks
from utils.utils import sleep
from utils.constants import ROLES, ZERO_ADDRESS, DAY, StrategyChangeType


def test_add_strategy__with_valid_strategy(chain, gov, vault, create_strategy):
    newStrategy = create_strategy(vault)

    snapshot = chain.pending_timestamp
    tx = vault.addStrategy(newStrategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyChanged))

    assert len(event) == 1
    assert event[0].strategy == newStrategy.address
    assert event[0].changeType == StrategyChangeType.ADDED

    strategyParams = vault.strategies(newStrategy)
    assert strategyParams.activation == pytest.approx(snapshot, abs=1)
    assert strategyParams.currentDebt == 0
    assert strategyParams.maxDebt == 0
    assert strategyParams.lastReport == pytest.approx(snapshot, abs=1)


def test_add_strategy__with_zero_address__fails_with_error(gov, vault):
    with ape.reverts("strategy cannot be zero address"):
        vault.addStrategy(ZERO_ADDRESS, sender=gov)


def test_add_strategy__with_activation__fails_with_error(gov, vault, strategy):
    with ape.reverts("strategy already active"):
        vault.addStrategy(strategy.address, sender=gov)


def test_add_strategy__with_incorrect_asset__fails_with_error(
    gov, vault, create_strategy, mock_token, create_vault
):
    # create strategy with same vault but diff asset
    other_vault = create_vault(mock_token)
    mock_token_strategy = create_strategy(other_vault)

    with ape.reverts("invalid asset"):
        vault.addStrategy(mock_token_strategy.address, sender=gov)


def test_add_strategy__with_generic_strategy(
    gov, vault, asset, create_generic_strategy
):
    # create strategy with no vault but same asset
    strategy = create_generic_strategy(asset)

    snapshot = chain.pending_timestamp
    tx = vault.addStrategy(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyChanged))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].changeType == StrategyChangeType.ADDED

    strategyParams = vault.strategies(strategy)
    assert strategyParams.activation == pytest.approx(snapshot, abs=1)
    assert strategyParams.currentDebt == 0
    assert strategyParams.maxDebt == 0
    assert strategyParams.lastReport == pytest.approx(snapshot, abs=1)


def test_revoke_strategy__with_existing_strategy(gov, vault, strategy):
    tx = vault.revokeStrategy(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyChanged))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].changeType == StrategyChangeType.REVOKED

    strategyParams = vault.strategies(strategy)
    checks.check_revoked_strategy(strategyParams)


def test_revoke_strategy__with_non_zero_debt__fails_with_error(
    gov, asset, vault, strategy, mint_and_deposit_into_vault, add_debt_to_strategy
):
    mint_and_deposit_into_vault(vault)
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance

    add_debt_to_strategy(gov, strategy, vault, newDebt)

    with ape.reverts("strategy has debt"):
        vault.revokeStrategy(strategy.address, sender=gov)


def test_revoke_strategy__with_inactive_strategy__fails_with_error(
    gov, vault, create_strategy
):
    strategy = create_strategy(vault)

    with ape.reverts("strategy not active"):
        vault.revokeStrategy(strategy.address, sender=gov)


def test_force_revoke_strategy__with_existing_strategy(gov, vault, strategy):
    tx = vault.forceRevokeStrategy(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyChanged))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].changeType == StrategyChangeType.REVOKED

    strategyParams = vault.strategies(strategy)
    checks.check_revoked_strategy(strategyParams)


def test_force_revoke_strategy__with_non_zero_debt(
    gov, asset, vault, strategy, mint_and_deposit_into_vault, add_debt_to_strategy
):
    mint_and_deposit_into_vault(vault)
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance

    add_debt_to_strategy(gov, strategy, vault, newDebt)

    tx = vault.forceRevokeStrategy(strategy.address, sender=gov)

    # strategy report error
    event = list(tx.decode_logs(vault.StrategyReported))
    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == 0
    assert event[0].loss == newDebt
    assert event[0].currentDebt == 0
    assert event[0].totalFees == 0
    assert event[0].totalRefunds == 0

    # strategy changed event
    event = list(tx.decode_logs(vault.StrategyChanged))
    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].changeType == StrategyChangeType.REVOKED

    assert vault.totalDebt() == 0
    assert vault.pricePerShare() == 0

    strategyParams = vault.strategies(strategy)
    checks.check_revoked_strategy(strategyParams)


def test_force_revoke_strategy__with_inactive_strategy__fails_with_error(
    gov, vault, create_strategy
):
    strategy = create_strategy(vault)

    with ape.reverts("strategy not active"):
        vault.forceRevokeStrategy(strategy.address, sender=gov)
