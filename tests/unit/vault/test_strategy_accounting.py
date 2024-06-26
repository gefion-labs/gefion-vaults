import ape
import pytest
from utils.constants import YEAR, DAY, ROLES, MAX_BPS_ACCOUNTANT, WEEK, MAX_INT
from utils.utils import days_to_secs


@pytest.fixture(autouse=True)
def seed_vault_with_funds(mint_and_deposit_into_vault, vault, gov):
    mint_and_deposit_into_vault(vault, gov, 10**18, 10**18 // 2)


@pytest.fixture(autouse=True)
def setRole(vault, gov):
    vault.setRole(
        gov.address,
        ROLES.EMERGENCY_MANAGER
        | ROLES.ADD_STRATEGY_MANAGER
        | ROLES.REVOKE_STRATEGY_MANAGER
        | ROLES.DEBT_MANAGER
        | ROLES.DEPOSIT_LIMIT_MANAGER
        | ROLES.MAX_DEBT_MANAGER
        | ROLES.ACCOUNTANT_MANAGER
        | ROLES.REPORTING_MANAGER,
        sender=gov,
    )


def test_process_report__with_inactive_strategy__reverts(gov, vault, create_strategy):
    strategy = create_strategy(vault)

    with ape.reverts("inactive strategy"):
        vault.processReport(strategy.address, sender=gov)


def test_process_report__with_gain_and_zero_fees(
    chain, gov, asset, vault, strategy, airdrop_asset, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    gain = newDebt // 2

    # add debt to strategy
    add_debt_to_strategy(gov, strategy, vault, newDebt)
    airdrop_asset(gov, asset, strategy, gain)
    # record gain
    strategy.report(sender=gov)

    strategyParams = vault.strategies(strategy.address)
    initial_debt = strategyParams.currentDebt

    snapshot = chain.pending_timestamp
    tx = vault.processReport(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == gain
    assert event[0].loss == 0
    assert event[0].currentDebt == initial_debt + gain
    assert event[0].totalFees == 0

    strategyParams = vault.strategies(strategy.address)
    assert strategyParams.currentDebt == initial_debt + gain
    assert vault.strategies(strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )


def test_process_report__with_gain_and_zero_management_fees(
    chain,
    gov,
    asset,
    vault,
    strategy,
    deploy_accountant,
    airdrop_asset,
    set_fees_for_strategy,
    add_debt_to_strategy,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    gain = newDebt // 2
    managementFee = 0
    performanceFee = 5_000
    total_fee = gain // 2

    accountant = deploy_accountant(vault)
    # add debt to strategy
    add_debt_to_strategy(gov, strategy, vault, newDebt)
    # airdrop gain to strategy
    airdrop_asset(gov, asset, strategy, gain)
    # record gain
    strategy.report(sender=gov)
    # set up accountant
    set_fees_for_strategy(gov, strategy, accountant, managementFee, performanceFee)

    strategyParams = vault.strategies(strategy.address)
    initial_debt = strategyParams.currentDebt

    snapshot = chain.pending_timestamp
    tx = vault.processReport(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == gain
    assert event[0].loss == 0
    assert event[0].currentDebt == initial_debt + gain
    assert event[0].totalFees == total_fee

    strategyParams = vault.strategies(strategy.address)
    assert strategyParams.currentDebt == initial_debt + gain
    assert vault.strategies(strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )

    chain.pending_timestamp = chain.pending_timestamp + days_to_secs(14)
    # chain.mine(timestamp=chain.pending_timestamp)
    # Vault mints shares worth the fees to the accountant
    accountant_balance = vault.balanceOf(accountant)
    assert (
        pytest.approx(vault.convertToAssets(accountant_balance), rel=1e-5) == total_fee
    )


def test_process_report__with_gain_and_zero_performance_fees(
    chain,
    gov,
    asset,
    vault,
    strategy,
    deploy_accountant,
    airdrop_asset,
    set_fees_for_strategy,
    add_debt_to_strategy,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    gain = newDebt // 2
    managementFee = 1000
    performanceFee = 0
    total_fee = vault_balance // 10  # 10% mgmt fee over all assets, over a year

    initial_total_assets = vault.totalAssets()
    initial_total_supply = vault.totalSupply()

    accountant = deploy_accountant(vault)
    # add debt to strategy
    add_debt_to_strategy(gov, strategy, vault, newDebt)
    # airdrop gain to strategy
    airdrop_asset(gov, asset, strategy, gain)
    # record gain
    strategy.report(sender=gov)
    # set up accountant
    set_fees_for_strategy(gov, strategy, accountant, managementFee, performanceFee)

    strategyParams = vault.strategies(strategy.address)
    initial_debt = strategyParams.currentDebt

    chain.pending_timestamp += YEAR
    snapshot = chain.pending_timestamp
    tx = vault.processReport(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == gain
    assert event[0].loss == 0
    assert event[0].currentDebt == initial_debt + gain
    assert event[0].totalFees == pytest.approx(total_fee, rel=1e-4)

    strategyParams = vault.strategies(strategy.address)
    assert strategyParams.currentDebt == initial_debt + gain
    assert vault.strategies(strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )

    # Vault mints shares worth the fees to the accountant
    accountant_balance = vault.balanceOf(accountant)
    assert (
        pytest.approx(vault.convertToAssets(accountant_balance), rel=1e-5) == total_fee
    )


def test_process_report__with_gain_and_both_fees(
    chain,
    gov,
    asset,
    vault,
    strategy,
    deploy_accountant,
    airdrop_asset,
    set_fees_for_strategy,
    add_debt_to_strategy,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    gain = newDebt // 2
    managementFee = 2500
    performanceFee = 2500
    total_fee = gain // 4

    initial_total_assets = vault.totalAssets()
    initial_total_supply = vault.totalSupply()

    accountant = deploy_accountant(vault)
    # add debt to strategy
    add_debt_to_strategy(gov, strategy, vault, newDebt)
    # airdrop gain to strategy
    airdrop_asset(gov, asset, strategy, gain)
    # record gain
    strategy.report(sender=gov)
    # set up accountant
    set_fees_for_strategy(gov, strategy, accountant, managementFee, performanceFee)

    strategyParams = vault.strategies(strategy.address)
    initial_debt = strategyParams.currentDebt

    snapshot = chain.pending_timestamp
    tx = vault.processReport(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == gain
    assert event[0].loss == 0
    assert event[0].currentDebt == initial_debt + gain
    assert event[0].totalFees == pytest.approx(total_fee, rel=1e-4)

    strategyParams = vault.strategies(strategy.address)
    assert strategyParams.currentDebt == initial_debt + gain
    assert vault.strategies(strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )

    # Vault mints shares worth the fees to the accountant
    accountant_balance = vault.balanceOf(accountant)
    assert (
        pytest.approx(vault.convertToAssets(accountant_balance), rel=1e-5) == total_fee
    )


def test_process_report__with_fees_exceeding_fee_cap(
    chain,
    gov,
    asset,
    vault,
    strategy,
    deploy_accountant,
    airdrop_asset,
    set_fees_for_strategy,
    add_debt_to_strategy,
):
    # test that fees are capped to 75% of gains
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    gain = newDebt // 2
    managementFee = 5000
    performanceFee = 5000
    max_fee = gain * 3 // 4  # max fee set at 3/4

    accountant = deploy_accountant(vault)
    # add debt to strategy
    add_debt_to_strategy(gov, strategy, vault, newDebt)
    # airdrop gain to strategy
    airdrop_asset(gov, asset, strategy, gain)
    # record gain
    strategy.report(sender=gov)
    # set up accountant
    set_fees_for_strategy(gov, strategy, accountant, managementFee, performanceFee)

    strategyParams = vault.strategies(strategy.address)
    initial_debt = strategyParams.currentDebt

    chain.pending_timestamp += YEAR  # need time to pass to accrue more fees
    snapshot = chain.pending_timestamp
    tx = vault.processReport(strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == strategy.address
    assert event[0].gain == gain
    assert event[0].loss == 0
    assert event[0].currentDebt == initial_debt + gain
    assert event[0].totalFees == max_fee

    strategyParams = vault.strategies(strategy.address)
    assert strategyParams.currentDebt == initial_debt + gain
    assert vault.strategies(strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )

    # Vault mints shares worth the fees to the accountant
    accountant_balance = vault.balanceOf(accountant)
    assert pytest.approx(vault.convertToAssets(accountant_balance), rel=1e-5) == max_fee


def test_process_report__with_loss(
    chain, gov, asset, vault, lossy_strategy, add_debt_to_strategy
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    loss = newDebt // 2

    # add debt to strategy and incur loss
    add_debt_to_strategy(gov, lossy_strategy, vault, newDebt)
    lossy_strategy.setLoss(gov.address, loss, sender=gov)

    strategyParams = vault.strategies(lossy_strategy.address)
    initial_debt = strategyParams.currentDebt

    snapshot = chain.pending_timestamp
    tx = vault.processReport(lossy_strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalFees == 0

    strategyParams = vault.strategies(lossy_strategy.address)
    assert strategyParams.currentDebt == initial_debt - loss
    assert vault.strategies(lossy_strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )
    assert vault.pricePerShare() / 10 ** vault.decimals() == 0.5


def test_process_report__with_loss_and_management_fees(
    chain,
    gov,
    asset,
    vault,
    lossy_strategy,
    add_debt_to_strategy,
    set_fees_for_strategy,
    deploy_accountant,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    loss = newDebt // 2
    managementFee = 1000
    performanceFee = 0
    refundRatio = 0

    accountant = deploy_accountant(vault)
    # set up accountant
    set_fees_for_strategy(
        gov, lossy_strategy, accountant, managementFee, performanceFee, refundRatio
    )

    # add debt to strategy and incur loss
    add_debt_to_strategy(gov, lossy_strategy, vault, newDebt)
    lossy_strategy.setLoss(gov.address, loss, sender=gov)

    strategyParams = vault.strategies(lossy_strategy.address)
    initial_debt = strategyParams.currentDebt

    # Management fees relay on duration of invest, so we need to advance in time to see results
    initial_timestamp = chain.pending_timestamp
    initial_pps = vault.pricePerShare()
    chain.mine(timestamp=initial_timestamp + YEAR)
    initial_total_assets = vault.totalAssets()

    expected_management_fees = vault_balance // 10

    # with a loss we will not get the full expected fee
    expected_management_fees = (
        (initial_total_assets - loss)
        / (initial_total_assets + expected_management_fees)
        * expected_management_fees
    )

    snapshot = chain.pending_timestamp

    tx = vault.processReport(lossy_strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalFees == pytest.approx(expected_management_fees, rel=1e-5)

    strategyParams = vault.strategies(lossy_strategy.address)

    assert strategyParams.currentDebt == initial_debt - loss
    assert vault.strategies(lossy_strategy.address).lastReport == pytest.approx(
        snapshot, abs=1
    )
    assert vault.convertToAssets(vault.balanceOf(accountant)) == pytest.approx(
        expected_management_fees, rel=1e-5
    )

    # Without fees, pps would be 0.5, as loss is half of debt, but with fees pps should be even lower
    assert vault.pricePerShare() / 10 ** vault.decimals() < initial_pps / 2
    assert vault.totalAssets() == pytest.approx(initial_total_assets - loss, 1e-5)


def test_process_report__with_loss_and_refunds(
    chain,
    gov,
    asset,
    vault,
    lossy_strategy,
    add_debt_to_strategy,
    set_fees_for_strategy,
    deploy_accountant,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    loss = newDebt // 2
    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000

    accountant = deploy_accountant(vault)
    # set up accountant
    asset.mint(accountant, loss, sender=gov)

    set_fees_for_strategy(
        gov, lossy_strategy, accountant, managementFee, performanceFee, refundRatio
    )

    # add debt to strategy and incur loss
    add_debt_to_strategy(gov, lossy_strategy, vault, newDebt)
    lossy_strategy.setLoss(gov.address, loss, sender=gov)

    strategyParams = vault.strategies(lossy_strategy.address)
    initial_debt = strategyParams.currentDebt

    pps_before_loss = vault.pricePerShare()
    assets_before_loss = vault.totalAssets()
    supply_before_loss = vault.totalSupply()
    tx = vault.processReport(lossy_strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalFees == 0
    assert event[0].totalRefunds == loss

    # Due to refunds, pps should be the same as before the loss
    assert vault.pricePerShare() == pps_before_loss
    assert vault.totalAssets() == assets_before_loss
    assert vault.totalSupply() == supply_before_loss
    assert vault.totalDebt() == newDebt - loss
    assert vault.totalIdle() == loss


def test_process_report__with_loss_management_fees_and_refunds(
    chain,
    gov,
    asset,
    vault,
    create_lossy_strategy,
    add_debt_to_strategy,
    set_fees_for_strategy,
    deploy_accountant,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    loss = newDebt // 2
    managementFee = 10_000
    performanceFee = 0
    refundRatio = 10_000

    lossy_strategy = create_lossy_strategy(vault)
    vault.addStrategy(lossy_strategy.address, sender=gov)
    initial_timestamp = chain.pending_timestamp
    lossy_strategy.setMaxDebt(MAX_INT, sender=gov)
    accountant = deploy_accountant(vault)
    # set up accountant
    asset.mint(accountant, loss, sender=gov)

    set_fees_for_strategy(
        gov, lossy_strategy, accountant, managementFee, performanceFee, refundRatio
    )

    # add debt to strategy and incur loss
    add_debt_to_strategy(gov, lossy_strategy, vault, newDebt)

    lossy_strategy.setLoss(gov.address, loss, sender=gov)

    strategyParams = vault.strategies(lossy_strategy.address)
    initial_debt = strategyParams.currentDebt
    pps_before_loss = vault.pricePerShare()
    assets_before_loss = vault.totalAssets()

    # let one day pass
    chain.pending_timestamp = initial_timestamp + DAY
    chain.mine(timestamp=chain.pending_timestamp)

    expected_management_fees = (
        newDebt
        * (chain.pending_timestamp - vault.strategies(lossy_strategy).lastReport)
        * managementFee
        / MAX_BPS_ACCOUNTANT
        / YEAR
    )

    # with a loss we will not get the full expected fee
    expected_management_fees = (
        newDebt / (newDebt + expected_management_fees) * expected_management_fees
    )

    tx = vault.processReport(lossy_strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalFees == pytest.approx(expected_management_fees, 1e-4)
    assert event[0].totalRefunds == loss

    # Due to fees, pps should be slightly below 1
    assert vault.pricePerShare() < pps_before_loss
    # Shares were minted at 1:1
    assert vault.convertToAssets(vault.balanceOf(accountant)) == pytest.approx(
        expected_management_fees, 1e-4
    )


def test_process_report__with_loss_and_refunds__not_enough_asset(
    chain,
    gov,
    asset,
    vault,
    lossy_strategy,
    add_debt_to_strategy,
    set_fees_for_strategy,
    deploy_accountant,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    loss = newDebt // 2
    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000

    accountant = deploy_accountant(vault)
    # set up accountant with not enough funds
    actual_refund = loss // 2
    asset.mint(accountant, actual_refund, sender=gov)

    set_fees_for_strategy(
        gov, lossy_strategy, accountant, managementFee, performanceFee, refundRatio
    )

    # add debt to strategy and incur loss
    add_debt_to_strategy(gov, lossy_strategy, vault, newDebt)
    lossy_strategy.setLoss(gov.address, loss, sender=gov)

    strategyParams = vault.strategies(lossy_strategy.address)
    initial_debt = strategyParams.currentDebt

    pps_before_loss = vault.pricePerShare()
    assets_before_loss = vault.totalAssets()
    supply_before_loss = vault.totalSupply()
    tx = vault.processReport(lossy_strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalFees == 0
    assert event[0].totalRefunds == actual_refund

    # Due to refunds, pps should be the same as before the loss
    assert vault.pricePerShare() < pps_before_loss
    assert vault.totalAssets() == assets_before_loss - (loss - actual_refund)
    assert vault.totalSupply() == supply_before_loss
    assert vault.totalDebt() == newDebt - loss
    assert vault.totalIdle() == actual_refund


def test_process_report__with_loss_and_refunds__not_enough_allowance(
    chain,
    gov,
    asset,
    vault,
    lossy_strategy,
    add_debt_to_strategy,
    set_fees_for_strategy,
    deploy_faulty_accountant,
):
    vault_balance = asset.balanceOf(vault)
    newDebt = vault_balance
    loss = newDebt // 2
    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000

    accountant = deploy_faulty_accountant(vault)
    # set up accountant with not enough funds
    actual_refund = loss // 2
    asset.mint(accountant, loss, sender=gov)

    set_fees_for_strategy(
        gov, lossy_strategy, accountant, managementFee, performanceFee, refundRatio
    )

    # add debt to strategy and incur loss
    add_debt_to_strategy(gov, lossy_strategy, vault, newDebt)
    lossy_strategy.setLoss(gov.address, loss, sender=gov)

    strategyParams = vault.strategies(lossy_strategy.address)
    initial_debt = strategyParams.currentDebt

    # Set approval below the intended refunds
    asset.approve(vault.address, actual_refund, sender=accountant)

    pps_before_loss = vault.pricePerShare()
    assets_before_loss = vault.totalAssets()
    supply_before_loss = vault.totalSupply()
    tx = vault.processReport(lossy_strategy.address, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert len(event) == 1
    assert event[0].strategy == lossy_strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalFees == 0
    assert event[0].totalRefunds == actual_refund

    # Due to refunds, pps should be the same as before the loss
    assert vault.pricePerShare() < pps_before_loss
    assert vault.totalAssets() == assets_before_loss - (loss - actual_refund)
    assert vault.totalSupply() == supply_before_loss
    assert vault.totalDebt() == newDebt - loss
    assert vault.totalIdle() == actual_refund


def test_set_accountant__with_accountant(gov, vault, deploy_accountant):
    accountant = deploy_accountant(vault)
    tx = vault.setAccountant(accountant.address, sender=gov)
    event = list(tx.decode_logs(vault.UpdateAccountant))

    assert len(event) == 1
    assert event[0].accountant == accountant.address

    assert vault.accountant() == accountant.address
