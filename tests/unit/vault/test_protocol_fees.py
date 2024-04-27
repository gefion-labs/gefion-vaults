from ape import chain
import pytest
from utils.constants import ROLES, YEAR, MAX_BPS_ACCOUNTANT
from utils.utils import days_to_secs


def test__report_with_no_protocolFees__no_accountant_fees(
    vault_factory,
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
):
    amount = fish_amount // 10

    assert vault_factory.protocolFeeConfig().feeBps == 0

    vault = create_vault(asset)
    strategy = create_strategy(vault)

    # Deposit assets to vault and get strategy ready
    user_deposit(fish, vault, asset, amount)
    add_strategy_to_vault(gov, strategy, vault)
    add_debt_to_strategy(gov, strategy, vault, amount)

    assert vault.pricePerShare() == int(10 ** vault.decimals())
    # We increase time after profit has been released and check estimation
    tx = vault.processReport(strategy, sender=gov)

    event = list(tx.decode_logs(vault.StrategyReported))
    assert event[0].protocolFees == 0

    shares_protocol = vault.balanceOf(gov.address)
    assert vault.convertToAssets(shares_protocol) == 0
    assert vault.pricePerShare() == int(10 ** vault.decimals())


def test__report_gain_with_protocolFees__accountant_fees(
    vault_factory,
    set_factory_fee_config,
    initial_set_up,
    asset,
    fish_amount,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
):
    amount = fish_amount // 10
    profit = int(amount * 0.1)

    # Set protocol to 10% for easy calculations.
    protocol_fee = 1_000
    managementFee = 0
    performanceFee = 1_000
    refundRatio = 0
    protocol_recipient = gov

    # set fees
    set_factory_fee_config(protocol_fee, protocol_recipient)

    # Deposit assets to vault and get strategy ready. Management fee == 0 initially
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )

    # Create a profit
    airdrop_asset(gov, asset, strategy, profit)
    strategy.report(sender=gov)

    expected_accountant_fee = profit * performanceFee / MAX_BPS_ACCOUNTANT
    expected_protocol_fee = expected_accountant_fee * protocol_fee / MAX_BPS_ACCOUNTANT

    price_per_share_pre = vault.pricePerShare()

    assert vault.pricePerShare() == int(10 ** vault.decimals())

    tx = vault.processReport(strategy, sender=gov)

    event = list(tx.decode_logs(vault.StrategyReported))
    assert event[0].protocolFees == expected_protocol_fee

    shares_protocol = vault.balanceOf(gov.address)
    assert (
        price_per_share_pre * shares_protocol // (10 ** vault.decimals())
        == expected_protocol_fee
    )
    assert vault.pricePerShare() == int(10 ** vault.decimals())


def test__report_no_gain_with_protocolFees__accountant_fees(
    vault_factory,
    set_factory_fee_config,
    initial_set_up,
    asset,
    fish_amount,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
):
    amount = fish_amount // 10
    profit = 0

    # Set protocol to 10% for easy calculations.
    protocol_fee = 1_000
    managementFee = 0
    performanceFee = 1_000
    refundRatio = 0
    protocol_recipient = gov

    # set fees
    set_factory_fee_config(protocol_fee, protocol_recipient)

    # Deposit assets to vault and get strategy ready. Management fee == 0 initially
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )

    expected_accountant_fee = profit * performanceFee / MAX_BPS_ACCOUNTANT
    expected_protocol_fee = expected_accountant_fee * protocol_fee / MAX_BPS_ACCOUNTANT

    price_per_share_pre = vault.pricePerShare()

    assert vault.pricePerShare() == int(10 ** vault.decimals())

    tx = vault.processReport(strategy, sender=gov)

    event = list(tx.decode_logs(vault.StrategyReported))
    assert event[0].protocolFees == expected_protocol_fee

    shares_protocol = vault.balanceOf(gov.address)
    assert (
        price_per_share_pre * shares_protocol // (10 ** vault.decimals())
        == expected_protocol_fee
    )
    assert vault.pricePerShare() == int(10 ** vault.decimals())


def test__report_gain_with_protocolFees__no_accountant_fees(
    vault_factory,
    set_factory_fee_config,
    initial_set_up,
    asset,
    fish_amount,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
):
    amount = fish_amount // 10
    profit = int(amount * 0.1)

    # Set protocol to 10% for easy calculations.
    protocol_fee = 1_000
    managementFee = 0
    performanceFee = 0
    refundRatio = 0
    protocol_recipient = gov

    # set fees
    set_factory_fee_config(protocol_fee, protocol_recipient)

    # Deposit assets to vault and get strategy ready. Management fee == 0 initially
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )

    # Create a profit
    airdrop_asset(gov, asset, strategy, profit)

    expected_accountant_fee = profit * performanceFee / MAX_BPS_ACCOUNTANT
    expected_protocol_fee = expected_accountant_fee * protocol_fee / MAX_BPS_ACCOUNTANT

    price_per_share_pre = vault.pricePerShare()

    assert vault.pricePerShare() == int(10 ** vault.decimals())

    tx = vault.processReport(strategy, sender=gov)

    event = list(tx.decode_logs(vault.StrategyReported))
    assert event[0].protocolFees == expected_protocol_fee

    shares_protocol = vault.balanceOf(gov.address)
    assert (
        price_per_share_pre * shares_protocol // (10 ** vault.decimals())
        == expected_protocol_fee
    )
    assert vault.pricePerShare() == int(10 ** vault.decimals())
