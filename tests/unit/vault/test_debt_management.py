import ape
import pytest
from utils.constants import DAY


@pytest.fixture(autouse=True)
def seed_vault_with_funds(mint_and_deposit_into_vault, vault, gov):
    mint_and_deposit_into_vault(vault, gov, 10**18, 10**18 // 2)


@pytest.mark.parametrize("maxDebt", [0, 10**22])
def test_update_maxDebt__with_debt_value(gov, vault, strategy, maxDebt):
    vault.updateMaxDebtForStrategy(strategy.address, maxDebt, sender=gov)

    assert vault.strategies(strategy.address).maxDebt == maxDebt


def test_update_maxDebt__with_inactive_strategy(gov, vault, create_strategy):
    strategy = create_strategy(vault)
    maxDebt = 10**18

    with ape.reverts("inactive strategy"):
        vault.updateMaxDebtForStrategy(strategy.address, maxDebt, sender=gov)


def test_update_debt__without_permission__reverts(gov, vault, asset, strategy, bunny):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance // 2
    currentDebt = vault.strategies(strategy.address).currentDebt

    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)
    with ape.reverts():
        vault.updateDebt(strategy.address, newDebt, sender=bunny)


def test_update_debt__with_strategy_maxDebt_less_than_newDebt__reverts(
    gov, asset, vault, strategy
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance // 2

    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    with ape.reverts("target debt higher than max debt"):
        vault.updateDebt(strategy.address, newDebt + 1, sender=gov)


def test_update_debt__with_currentDebt_less_than_newDebt(gov, asset, vault, strategy):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance // 2
    currentDebt = vault.strategies(strategy.address).currentDebt
    difference = newDebt - currentDebt
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    tx = vault.updateDebt(strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    assert vault.strategies(strategy.address).currentDebt == newDebt
    assert asset.balanceOf(strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - newDebt)
    assert vault.totalIdle() == initial_idle - difference
    assert vault.totalDebt() == initial_debt + difference


def test_update_debt__with_currentDebt_equal_to_newDebt__reverts(
    gov, asset, vault, strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance // 2

    add_debt_to_strategy(gov, strategy, vault, newDebt)

    with ape.reverts("new debt equals current debt"):
        vault.updateDebt(strategy.address, newDebt, sender=gov)


def test_update_debt__with_currentDebt_greater_than_newDebt_and_zero_withdrawable__reverts(
    gov, asset, vault, locked_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    newDebt = vault_balance // 2

    add_debt_to_strategy(gov, locked_strategy, vault, currentDebt)
    # lock funds to set withdrawable to zero
    locked_strategy.setLockedFunds(currentDebt, DAY, sender=gov)
    # reduce debt in strategy
    vault.updateMaxDebtForStrategy(locked_strategy.address, newDebt, sender=gov)

    with ape.reverts("nothing to withdraw"):
        vault.updateDebt(locked_strategy.address, newDebt, sender=gov)


def test_update_debt__with_currentDebt_greater_than_newDebt_and_strategy_has_losses__reverts(
    gov, asset, vault, lossy_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    newDebt = vault_balance // 2
    loss = int(vault_balance * 0.1)

    add_debt_to_strategy(gov, lossy_strategy, vault, currentDebt)

    lossy_strategy.setLoss(gov, loss, sender=gov)

    with ape.reverts("strategy has unrealised losses"):
        vault.updateDebt(lossy_strategy.address, newDebt, sender=gov)


def test_update_debt__with_currentDebt_greater_than_newDebt_and_insufficient_withdrawable(
    gov, asset, vault, locked_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    locked_debt = currentDebt // 2
    newDebt = vault_balance // 4
    difference = currentDebt - locked_debt  # maximum we can withdraw

    add_debt_to_strategy(gov, locked_strategy, vault, currentDebt)

    # reduce debt in strategy
    vault.updateMaxDebtForStrategy(locked_strategy.address, newDebt, sender=gov)
    # lock portion of funds to reduce withdrawable
    locked_strategy.setLockedFunds(locked_debt, DAY, sender=gov)
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    tx = vault.updateDebt(locked_strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == locked_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == locked_debt

    assert vault.strategies(locked_strategy.address).currentDebt == locked_debt
    assert asset.balanceOf(locked_strategy) == locked_debt
    assert asset.balanceOf(vault) == (vault_balance - locked_debt)
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == initial_debt - difference


def test_update_debt__with_currentDebt_greater_than_newDebt_and_sufficient_withdrawable(
    gov, asset, vault, strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    newDebt = vault_balance // 2
    difference = currentDebt - newDebt

    add_debt_to_strategy(gov, strategy, vault, currentDebt)
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    # reduce debt in strategy
    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    tx = vault.updateDebt(strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    assert vault.strategies(strategy.address).currentDebt == newDebt
    assert asset.balanceOf(strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - newDebt)
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == initial_debt - difference


def test_update_debt__with_newDebt_greater_than_max_desired_debt(
    gov, asset, vault, strategy
):
    vault_balance = asset.balanceOf(vault)
    maxDebt = vault_balance
    max_desired_debt = vault_balance // 2
    currentDebt = vault.strategies(strategy.address).currentDebt
    difference = max_desired_debt - currentDebt
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    vault.updateMaxDebtForStrategy(strategy.address, maxDebt, sender=gov)
    strategy.setMaxDebt(max_desired_debt, sender=gov)

    # update debt
    tx = vault.updateDebt(strategy.address, maxDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == max_desired_debt

    assert vault.strategies(strategy.address).currentDebt == max_desired_debt
    assert asset.balanceOf(strategy) == max_desired_debt
    assert asset.balanceOf(vault) == (vault_balance - max_desired_debt)
    assert vault.totalIdle() == initial_idle - difference
    assert vault.totalDebt() == initial_debt + difference


@pytest.mark.parametrize("minimumTotalIdle", [0, 10**21])
def test_set_minimumTotalIdle__with_minimumTotalIdle(
    gov, vault, minimumTotalIdle
):

    tx = vault.setMinimumTotalIdle(minimumTotalIdle, sender=gov)
    assert vault.minimumTotalIdle() == minimumTotalIdle

    event = list(tx.decode_logs(vault.UpdateMinimumTotalIdle))
    assert len(event) == 1
    assert event[0].minimumTotalIdle == minimumTotalIdle


@pytest.mark.parametrize("minimumTotalIdle", [10**21])
def test_set_minimumTotalIdle__without_permission__reverts(
    accounts, vault, minimumTotalIdle
):
    """
    Only DEBT_MANAGER should be able to update minimumTotalIdle. Reverting if found any other sender.
    """
    with ape.reverts():
        vault.setMinimumTotalIdle(minimumTotalIdle, sender=accounts[-1])


def test_update_debt__with_currentDebt_less_than_newDebt_and_minimumTotalIdle(
    gov, asset, vault, strategy
):
    """
    Current debt is greater than new debt. Vault has a minimum total idle value small that does not affect the updateDebt method.
    """
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance // 2
    currentDebt = vault.strategies(strategy.address).currentDebt
    difference = newDebt - currentDebt
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    # set minimum total idle to a small value that doesn´t interfeer on updateDebt
    minimumTotalIdle = 1
    vault.setMinimumTotalIdle(minimumTotalIdle, sender=gov)
    assert vault.minimumTotalIdle() == 1

    # increase debt in strategy
    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    tx = vault.updateDebt(strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    assert vault.strategies(strategy.address).currentDebt == newDebt
    assert asset.balanceOf(strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - newDebt)
    assert vault.totalIdle() == initial_idle - difference
    assert vault.totalDebt() == initial_debt + difference

    assert vault.totalIdle() > vault.minimumTotalIdle()


def test_update_debt__with_currentDebt_less_than_newDebt_and_total_idle_lower_than_minimumTotalIdle__revert(
    gov, asset, vault, strategy
):
    """
    Current debt is greater than new debt. Vault has a total idle value lower/equal to minimum total idle value. It cannot provide more
    assets to the strategy as there are no funds, we are therefore reverting.
    """

    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance // 2

    minimumTotalIdle = vault.totalIdle()
    vault.setMinimumTotalIdle(minimumTotalIdle, sender=gov)
    assert vault.minimumTotalIdle() == vault.totalIdle()

    # increase debt in strategy
    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    with ape.reverts("no funds to deposit"):
        vault.updateDebt(strategy.address, newDebt, sender=gov)


def test_update_debt__with_currentDebt_less_than_newDebt_and_minimumTotalIdle_reducing_newDebt(
    gov, asset, vault, strategy
):
    """
    Current debt is lower than new debt. Value of minimum total idle reduces the amount of assets that the vault can provide.
    """

    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    currentDebt = vault.strategies(strategy.address).currentDebt

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    # we ensure a small amount of liquidity remains in the vault
    minimumTotalIdle = vault_balance - 1
    vault.setMinimumTotalIdle(minimumTotalIdle, sender=gov)
    assert vault.minimumTotalIdle() == vault_balance - 1

    # vault can give as much as it reaches minimumTotalIdle
    expected_new_differnce = initial_idle - minimumTotalIdle
    expected_newDebt = currentDebt + expected_new_differnce

    # increase debt in strategy
    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    tx = vault.updateDebt(strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == expected_newDebt

    assert vault.strategies(strategy.address).currentDebt == expected_newDebt
    assert asset.balanceOf(strategy) == expected_newDebt
    assert asset.balanceOf(vault) == vault_balance - expected_new_differnce
    assert vault.totalIdle() == initial_idle - expected_new_differnce
    assert vault.totalDebt() == initial_debt + expected_new_differnce


def test_update_debt__with_currentDebt_greater_than_newDebt_and_minimumTotalIdle(
    gov, asset, vault, strategy, add_debt_to_strategy
):
    """
    Current debt is greater than new debt. Vault has a minimum total idle value small that does not affect the updateDebt method.
    """
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    newDebt = vault_balance // 2
    difference = currentDebt - newDebt

    add_debt_to_strategy(gov, strategy, vault, currentDebt)

    # we compute vault values again, as they have changed
    vault_balance = asset.balanceOf(vault)
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    # small minimum total idle value not to interfeer with updateDebt method
    minimumTotalIdle = 1
    vault.setMinimumTotalIdle(minimumTotalIdle, sender=gov)

    assert vault.minimumTotalIdle() == 1

    # reduce debt in strategy
    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    tx = vault.updateDebt(strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    assert vault.strategies(strategy.address).currentDebt == newDebt
    assert asset.balanceOf(strategy) == newDebt
    assert asset.balanceOf(vault) == vault_balance + difference
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == initial_debt - difference


def test_update_debt__with_currentDebt_greater_than_newDebt_and_total_idle_less_than_minimumTotalIdle(
    gov, asset, vault, strategy, add_debt_to_strategy
):
    """
    Current debt is greater than new debt. Vault has a total idle value lower than its minimum total idle value.
    .updateDebt will reduce the new debt value to increase the amount of assets that its getting from the strategy and ensure that
    total idle value is greater than minimum total idle.
    """
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    newDebt = vault_balance // 3

    add_debt_to_strategy(gov, strategy, vault, currentDebt)

    # we compute vault values again, as they have changed
    vault_balance = asset.balanceOf(vault)
    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    # we set minimum total idle to a value greater than debt difference
    minimumTotalIdle = currentDebt - newDebt + 1
    vault.setMinimumTotalIdle(minimumTotalIdle, sender=gov)
    assert vault.minimumTotalIdle() == currentDebt - newDebt + 1

    # we compute expected changes in debt due to minimum total idle need
    expected_new_difference = minimumTotalIdle - initial_idle
    expected_newDebt = currentDebt - expected_new_difference

    # reduce debt in strategy
    vault.updateMaxDebtForStrategy(strategy.address, newDebt, sender=gov)

    tx = vault.updateDebt(strategy.address, newDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == expected_newDebt

    assert vault.strategies(strategy.address).currentDebt == expected_newDebt
    assert asset.balanceOf(strategy) == expected_newDebt
    assert asset.balanceOf(vault) == vault_balance + expected_new_difference
    assert vault.totalIdle() == initial_idle + expected_new_difference
    assert vault.totalDebt() == initial_debt - expected_new_difference


def test_update_debt__with_faulty_strategy_that_deposits_less_than_requested(
    gov, asset, vault, faulty_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    expected_debt = currentDebt // 2
    difference = currentDebt - expected_debt  # maximum we can withdraw

    add_debt_to_strategy(gov, faulty_strategy, vault, currentDebt)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    # check the strategy only took half and vault recorded it correctly
    assert initial_idle == expected_debt
    assert initial_debt == expected_debt
    assert vault.strategies(faulty_strategy.address).currentDebt == expected_debt
    assert asset.balanceOf(faulty_strategy) == expected_debt


def test_update_debt__with_lossy_strategy_that_withdraws_less_than_requested(
    gov, asset, vault, lossy_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)

    add_debt_to_strategy(gov, lossy_strategy, vault, vault_balance)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    currentDebt = vault.strategies(lossy_strategy.address).currentDebt
    loss = currentDebt // 10
    newDebt = 0
    difference = currentDebt - loss

    lossy_strategy.setWithdrawingLoss(loss, sender=gov)

    initial_pps = vault.pricePerShare()
    tx = vault.updateDebt(lossy_strategy.address, 0, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    # Should have recorded the loss
    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    # assert we got back 90% of requested and it recorded the loss.
    assert vault.pricePerShare() < initial_pps
    assert vault.strategies(lossy_strategy.address).currentDebt == newDebt
    assert asset.balanceOf(lossy_strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - loss)
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == newDebt


def test_update_debt__with_lossy_strategy_that_withdraws_less_than_requested__max_loss(
    gov, asset, vault, lossy_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)

    add_debt_to_strategy(gov, lossy_strategy, vault, vault_balance)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    currentDebt = vault.strategies(lossy_strategy.address).currentDebt
    loss = currentDebt // 10
    newDebt = 0
    difference = currentDebt - loss

    lossy_strategy.setWithdrawingLoss(loss, sender=gov)

    initial_pps = vault.pricePerShare()

    # With 0 max loss should revert.
    with ape.reverts("too much loss"):
        vault.updateDebt(lossy_strategy.address, 0, 0, sender=gov)

    # Up to the loss percent still reverts
    with ape.reverts("too much loss"):
        vault.updateDebt(lossy_strategy.address, 0, 999, sender=gov)

    # Over the loss percent will succeed and account correctly.
    tx = vault.updateDebt(lossy_strategy.address, 0, 1_000, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    # Should have recorded the loss
    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    # assert we got back 90% of requested and it recorded the loss.
    assert vault.pricePerShare() < initial_pps
    assert vault.strategies(lossy_strategy.address).currentDebt == newDebt
    assert asset.balanceOf(lossy_strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - loss)
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == newDebt


def test_update_debt__with_faulty_strategy_that_withdraws_more_than_requested__only_half_withdrawn(
    gov, asset, vault, lossy_strategy, add_debt_to_strategy, airdrop_asset
):
    vault_balance = asset.balanceOf(vault)

    add_debt_to_strategy(gov, lossy_strategy, vault, vault_balance)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    currentDebt = vault.strategies(lossy_strategy.address).currentDebt
    extra = currentDebt // 10
    targetDebt = currentDebt // 2
    newDebt = targetDebt - extra
    difference = currentDebt - newDebt

    airdrop_asset(gov, asset, lossy_strategy.yieldSource(), extra)
    lossy_strategy.setWithdrawingLoss(-extra, sender=gov)

    initial_pps = vault.pricePerShare()
    tx = vault.updateDebt(lossy_strategy.address, targetDebt, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    # Should have recorded the extra as idle
    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    # assert we recorded correctly
    assert vault.pricePerShare() == initial_pps
    assert vault.strategies(lossy_strategy.address).currentDebt == newDebt
    assert lossy_strategy.totalAssets() == targetDebt
    assert asset.balanceOf(vault) == difference
    assert vault.totalIdle() == difference
    assert vault.totalDebt() == newDebt


def test_update_debt__with_faulty_strategy_that_withdraws_more_than_requested(
    gov, asset, vault, lossy_strategy, add_debt_to_strategy, airdrop_asset
):
    vault_balance = asset.balanceOf(vault)

    add_debt_to_strategy(gov, lossy_strategy, vault, vault_balance)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    currentDebt = vault.strategies(lossy_strategy.address).currentDebt
    extra = currentDebt // 10
    newDebt = 0
    difference = currentDebt

    airdrop_asset(gov, asset, lossy_strategy.yieldSource(), extra)
    lossy_strategy.setWithdrawingLoss(-extra, sender=gov)

    initial_pps = vault.pricePerShare()
    tx = vault.updateDebt(lossy_strategy.address, 0, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    # Should have recorded normally
    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    assert vault.pricePerShare() == initial_pps
    assert vault.strategies(lossy_strategy.address).currentDebt == newDebt
    assert lossy_strategy.totalAssets() == newDebt
    assert asset.balanceOf(vault) == (vault_balance + extra)
    assert vault.totalIdle() == vault_balance
    assert vault.totalDebt() == newDebt


def test_update_debt__with_faulty_strategy_that_deposits_less_than_requested_with_airdrop(
    gov,
    asset,
    vault,
    faulty_strategy,
    add_debt_to_strategy,
    airdrop_asset,
    fish_amount,
):
    vault_balance = asset.balanceOf(vault)
    currentDebt = vault_balance
    expected_debt = currentDebt // 2
    difference = currentDebt - expected_debt  # maximum we can withdraw

    # airdrop some asset to the vault
    airdrop_asset(gov, asset, vault, fish_amount)

    add_debt_to_strategy(gov, faulty_strategy, vault, currentDebt)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()

    # check the strategy only took half and vault recorded it correctly
    assert initial_idle == expected_debt
    assert initial_debt == expected_debt
    assert vault.strategies(faulty_strategy.address).currentDebt == expected_debt
    assert asset.balanceOf(faulty_strategy) == expected_debt


def test_update_debt__with_lossy_strategy_that_withdraws_less_than_requested_with_airdrop(
    gov,
    asset,
    vault,
    lossy_strategy,
    add_debt_to_strategy,
    airdrop_asset,
    fish_amount,
):
    vault_balance = asset.balanceOf(vault)

    add_debt_to_strategy(gov, lossy_strategy, vault, vault_balance)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    currentDebt = vault.strategies(lossy_strategy.address).currentDebt
    loss = currentDebt // 10
    newDebt = 0
    difference = currentDebt - loss

    lossy_strategy.setWithdrawingLoss(loss, sender=gov)

    initial_pps = vault.pricePerShare()

    # airdrop some asset to the vault
    airdrop_asset(gov, asset, vault, fish_amount)

    tx = vault.updateDebt(lossy_strategy.address, 0, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    # assert we only got back half of what was requested and the vault recorded it correctly
    assert vault.pricePerShare() < initial_pps
    assert vault.strategies(lossy_strategy.address).currentDebt == newDebt
    assert asset.balanceOf(lossy_strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - loss + fish_amount)
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == newDebt


def test_update_debt__with_lossy_strategy_that_withdraws_less_than_requested_with_airdrop_and_max_loss(
    gov,
    asset,
    vault,
    lossy_strategy,
    add_debt_to_strategy,
    airdrop_asset,
    fish_amount,
):
    vault_balance = asset.balanceOf(vault)

    add_debt_to_strategy(gov, lossy_strategy, vault, vault_balance)

    initial_idle = vault.totalIdle()
    initial_debt = vault.totalDebt()
    currentDebt = vault.strategies(lossy_strategy.address).currentDebt
    loss = currentDebt // 10
    newDebt = 0
    difference = currentDebt - loss

    lossy_strategy.setWithdrawingLoss(loss, sender=gov)

    initial_pps = vault.pricePerShare()

    # airdrop some asset to the vault
    airdrop_asset(gov, asset, vault, fish_amount)

    # With 0 max loss should revert.
    with ape.reverts("too much loss"):
        vault.updateDebt(lossy_strategy.address, 0, 0, sender=gov)

    # Up to the loss percent still reverts
    with ape.reverts("too much loss"):
        vault.updateDebt(lossy_strategy.address, 0, 999, sender=gov)

    # At the amount doesn't revert
    tx = vault.updateDebt(lossy_strategy.address, 0, 1_000, sender=gov)
    event = list(tx.decode_logs(vault.DebtUpdated))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].currentDebt == currentDebt
    assert event[0].newDebt == newDebt

    # assert we only got back half of what was requested and the vault recorded it correctly
    assert vault.pricePerShare() < initial_pps
    assert vault.strategies(lossy_strategy.address).currentDebt == newDebt
    assert asset.balanceOf(lossy_strategy) == newDebt
    assert asset.balanceOf(vault) == (vault_balance - loss + fish_amount)
    assert vault.totalIdle() == initial_idle + difference
    assert vault.totalDebt() == newDebt
