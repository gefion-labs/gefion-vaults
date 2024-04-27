from utils.utils import days_to_secs
from utils.constants import MAX_BPS, MAX_BPS_ACCOUNTANT, WEEK, YEAR, DAY
from ape import chain, reverts
import pytest


############ HELPERS ############
def assert_strategy_reported(
    log, strategy_address, gain, loss, currentDebt, totalFees, totalRefunds
):
    assert log.strategy == strategy_address
    assert log.gain == gain
    assert log.loss == loss
    assert log.currentDebt == currentDebt
    assert pytest.approx(log.totalFees, abs=2) == totalFees
    assert log.totalRefunds == totalRefunds


def assert_price_per_share(vault, pps):
    assert (
        pytest.approx(vault.pricePerShare() / 10 ** vault.decimals(), rel=1e-4) == pps
    )


def create_and_check_profit(
    asset,
    strategy,
    gov,
    vault,
    profit,
    totalFees=0,
    totalRefunds=0,
    by_pass_fees=False,
):
    # We create a virtual profit
    initial_debt = vault.strategies(strategy).currentDebt
    asset.transfer(strategy, profit, sender=gov)
    # Record profits at the strategy level.
    strategy.report(sender=gov)
    tx = vault.processReport(strategy, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert_strategy_reported(
        event[0],
        strategy.address,
        profit,
        0,
        initial_debt + profit,
        totalFees if not by_pass_fees else event[0].totalFees,
        totalRefunds,
    )
    return event[0].totalFees


def create_and_check_loss(strategy, gov, vault, loss, totalRefunds=0):
    # We create a virtual profit
    initial_debt = vault.strategies(strategy).currentDebt

    strategy.setLoss(gov, loss, sender=gov)
    tx = vault.processReport(strategy, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))

    assert event[0].strategy == strategy.address
    assert event[0].gain == 0
    assert event[0].loss == loss
    assert event[0].currentDebt == initial_debt - loss
    assert event[0].totalRefunds == totalRefunds

    return event[0].totalFees


def check_vault_totals(vault, totalDebt, totalIdle, totalAssets, totalSupply):
    assert pytest.approx(vault.totalIdle(), abs=1) == totalIdle
    assert vault.totalDebt() == totalDebt
    assert pytest.approx(vault.totalAssets(), abs=1) == totalAssets
    # will adjust the accuracy based on token decimals
    assert (
        pytest.approx(vault.totalSupply(), rel=10 ** -(vault.decimals() * 2 // 3))
        == totalSupply
    )


def increase_time_and_check_profit_buffer(
    chain, vault, secs=days_to_secs(10), expected_buffer=0
):
    # We increase time after profit has been released and update strategy debt to 0
    chain.pending_timestamp = chain.pending_timestamp + secs - 1
    chain.mine(timestamp=chain.pending_timestamp)
    assert pytest.approx(vault.balanceOf(vault), rel=1e-4) == expected_buffer


############ TESTS ############


def test_gain_no_fees_no_refunds_no_existing_buffer(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)
    create_and_check_profit(asset, strategy, gov, vault, first_profit)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    increase_time_and_check_profit_buffer(chain, vault)

    assert_price_per_share(vault, 2.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 2.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit


def test_gain_no_fees_with_refunds_accountant_not_enough_shares(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000

    vault, strategy, accountant = initial_set_up(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=first_profit // 10,
    )

    create_and_check_profit(
        asset, strategy, gov, vault, first_profit, 0, first_profit // 10
    )

    # Refunds are nos as much as desired, as accountant has limited shares
    assert vault.balanceOf(vault) == first_profit + first_profit // 10

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=first_profit // 10,
        totalAssets=amount + first_profit + first_profit // 10,
        totalSupply=amount + first_profit + first_profit // 10,
    )


def test_gain_no_fees_with_refunds_no_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000

    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )
    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT
    create_and_check_profit(asset, strategy, gov, vault, first_profit, 0, totalRefunds)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit + totalRefunds,
    )
    assert vault.balanceOf(vault) == first_profit + totalRefunds
    assert vault.balanceOf(accountant) == 0

    increase_time_and_check_profit_buffer(chain, vault)
    assert_price_per_share(vault, 3.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount,
    )
    assert_price_per_share(vault, 3.0)
    assert vault.strategies(strategy).currentDebt == 0

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    assert asset.balanceOf(vault) == 0

    # User ends up with the initial deposit, the profit and the refunds
    assert asset.balanceOf(fish) == fish_amount + first_profit + totalRefunds

    # Accountant redeems shares
    with reverts("no shares to redeem"):
        vault.redeem(
            vault.balanceOf(accountant), accountant, accountant, sender=accountant
        )


def test_gain_no_fees_with_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000

    vault, strategy, accountant = initial_set_up(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=2 * amount,
    )

    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT
    create_and_check_profit(asset, strategy, gov, vault, first_profit, 0, totalRefunds)

    timestamp = chain.pending_timestamp
    assert_price_per_share(vault, 1.0)
    # total supply is equal to total assets due to the minting of shares to avoid instant pps
    # total supply will start to gradually decrease
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit + totalRefunds,
    )
    # the vault should have locked 100% of the profit + 100% of the refunds
    assert vault.balanceOf(vault) == first_profit + totalRefunds
    assert vault.balanceOf(accountant) == 0

    # We increase time after profit has been released
    # the buffer should be half locked
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit // 2 + totalRefunds // 2,
    )

    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()
    assert pytest.approx(pricePerShare, rel=1e-5) == (
        amount + first_profit + totalRefunds
    ) / (amount + first_profit - first_profit // 2 + totalRefunds - totalRefunds // 2)

    # check correct locked shares
    assert (
        pytest.approx(vault.balanceOf(vault), rel=1e-3)
        == first_profit // 2 + totalRefunds // 2
    )

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount
        + first_profit
        - first_profit // 2  # minted - unlocked
        + totalRefunds
        - totalRefunds // 2,  # minted - unlocked
    )

    # we create a second profit and refund 100% of profits again
    # refunds should be valued at new price per share:
    # (i.e. totalRefunds / pricePerShare)
    create_and_check_profit(
        asset, strategy, gov, vault, second_profit, 0, totalRefunds
    )

    time_passed = chain.pending_timestamp - timestamp
    assert_price_per_share(vault, pricePerShare)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=2 * totalRefunds,
        totalAssets=amount + first_profit + second_profit + 2 * totalRefunds,
        totalSupply=amount
        + first_profit
        - first_profit // (WEEK / time_passed)
        + totalRefunds
        - totalRefunds // (WEEK / time_passed)
        + vault.convertToShares(int(totalRefunds + second_profit)),
    )

    increase_time_and_check_profit_buffer(chain, vault)
    assert_price_per_share(vault, 5.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=2 * totalRefunds,
        totalAssets=amount + first_profit + second_profit + 2 * totalRefunds,
        totalSupply=amount,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit + 2 * totalRefunds,
        totalAssets=amount + first_profit + second_profit + 2 * totalRefunds,
        totalSupply=amount,
    )
    assert_price_per_share(vault, 5.0)
    assert vault.strategies(strategy).currentDebt == 0

    shares_fish = vault.balanceOf(fish)
    shares_accountant = vault.balanceOf(accountant)
    total_shares = vault.totalSupply()

    # Fish redeems shares
    vault.redeem(shares_fish, fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )

    assert asset.balanceOf(vault) == 0

    # User ends up with the initial deposit, the profit and the refunds
    assert pytest.approx(asset.balanceOf(fish), rel=1e-4) == (
        fish_amount + first_profit + second_profit + totalRefunds * 2
    )

    # Accountant redeems shares
    with reverts("no shares to redeem"):
        vault.redeem(
            vault.balanceOf(accountant), accountant, accountant, sender=accountant
        )


def test_gain_no_fees_no_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 0

    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )
    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT
    create_and_check_profit(asset, strategy, gov, vault, first_profit, 0, totalRefunds)
    timestamp = chain.pending_timestamp
    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    assert vault.balanceOf(vault) == first_profit

    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 2, expected_buffer=first_profit // 2
    )

    pricePerShare = vault.totalAssets() / (amount + first_profit - first_profit // 2)
    assert_price_per_share(vault, pricePerShare)

    # Create second profit
    create_and_check_profit(asset, strategy, gov, vault, second_profit, 0, 0)

    assert_price_per_share(vault, pricePerShare)

    time_passed = chain.pending_timestamp - timestamp
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount
        + first_profit
        - first_profit // (WEEK / time_passed)
        + vault.convertToShares(second_profit),
    )

    assert pytest.approx(
        vault.balanceOf(vault), rel=1e-4
    ) == first_profit // 2 + vault.convertToShares(second_profit)

    increase_time_and_check_profit_buffer(chain, vault)
    assert_price_per_share(vault, 3.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 3.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    # User gets all the profits
    assert asset.balanceOf(fish) == fish_amount + first_profit + second_profit


def test_gain_fees_no_refunds_no_existing_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    # Using only performanceFee as its easier to measure for tests
    managementFee = 0
    performanceFee = 1_000
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )
    create_and_check_profit(
        asset,
        strategy,
        gov,
        vault,
        first_profit,
        first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    assert vault.balanceOf(vault) == first_profit * (
        1 - performanceFee / MAX_BPS_ACCOUNTANT
    )
    fee_shares = first_profit * (performanceFee / MAX_BPS_ACCOUNTANT)
    assert vault.balanceOf(accountant) == fee_shares

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)

    assert pytest.approx(vault.pricePerShare() / 10 ** vault.decimals(), rel=1e-4) == (
        amount + first_profit
    ) / (amount + performanceFee * first_profit / MAX_BPS_ACCOUNTANT)

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    # Fish redeems shares
    tx = vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)
    withdraw_assets = list(tx.decode_logs(vault.Withdraw))[0].assets
    withdrawn_diff = int(
        amount
        + first_profit
        - first_profit * performanceFee // MAX_BPS_ACCOUNTANT
        - withdraw_assets
    )

    assert_price_per_share(vault, vault.totalAssets() / vault.balanceOf(accountant))

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=first_profit * performanceFee // MAX_BPS_ACCOUNTANT
        + withdrawn_diff,
        totalAssets=first_profit * performanceFee // MAX_BPS_ACCOUNTANT
        + withdrawn_diff,
        totalSupply=first_profit * performanceFee // MAX_BPS_ACCOUNTANT,
    )

    assert fish_amount < asset.balanceOf(fish)
    assert asset.balanceOf(fish) < fish_amount + first_profit

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)

    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    assert asset.balanceOf(vault) == 0


def test_gain_fees_refunds_no_existing_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    # Using only performanceFee as its easier to measure for tests
    managementFee = 0
    performanceFee = 1_000
    refundRatio = 10_000

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )

    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT

    create_and_check_profit(
        asset,
        strategy,
        gov,
        vault,
        first_profit,
        totalFees=first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
        totalRefunds=totalRefunds,
    )
    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit + totalRefunds,
    )
    assert (
        vault.balanceOf(vault)
        == first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) + totalRefunds
    )
    fee_shares = first_profit * performanceFee / MAX_BPS_ACCOUNTANT
    assert vault.balanceOf(accountant) == fee_shares

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)
    assert_price_per_share(
        vault, (amount + first_profit + totalRefunds) / (amount + fee_shares)
    )
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + fee_shares,
    )
    assert_price_per_share(
        vault, (amount + first_profit + totalRefunds) / (amount + fee_shares)
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, vault.totalAssets() / vault.balanceOf(accountant))
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=vault.convertToAssets(
            first_profit * performanceFee // MAX_BPS_ACCOUNTANT
        ),
        totalAssets=vault.convertToAssets(
            first_profit * performanceFee // MAX_BPS_ACCOUNTANT
        ),
        totalSupply=first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    # User gets profit plus refunds minus fees
    assert fish_amount < asset.balanceOf(fish)
    assert (
        pytest.approx(asset.balanceOf(fish), abs=1)
        == fish_amount
        + first_profit * (1 + refundRatio / MAX_BPS_ACCOUNTANT)
        - (amount + first_profit + totalRefunds)
        / (amount + fee_shares)
        * first_profit
        * performanceFee
        // MAX_BPS_ACCOUNTANT
    )

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)
    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    assert asset.balanceOf(vault) == 0


def test_gain_fees_with_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10

    managementFee = 0
    performanceFee = 1_000
    refundRatio = 10_000

    vault, strategy, accountant = initial_set_up(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=2 * amount,
    )

    totalFees = first_profit * performanceFee / MAX_BPS_ACCOUNTANT
    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT
    create_and_check_profit(
        asset, strategy, gov, vault, first_profit, totalFees, totalRefunds
    )

    timestamp = chain.pending_timestamp
    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit + totalRefunds,
    )
    assert vault.balanceOf(vault) == totalRefunds + first_profit * (
        1 - performanceFee / MAX_BPS_ACCOUNTANT
    )
    assert vault.balanceOf(accountant) == totalFees

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2
        + totalRefunds // 2,
    )

    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()
    assert pricePerShare < 2.0
    assert (
        pytest.approx(vault.balanceOf(vault), rel=1e-3)
        == first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2
        + totalRefunds // 2
    )
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount
        + first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2
        + totalRefunds
        - totalRefunds // 2
        + totalFees,
    )

    total_second_fees = second_profit * performanceFee / MAX_BPS_ACCOUNTANT
    total_second_refunds = second_profit * refundRatio / MAX_BPS_ACCOUNTANT

    create_and_check_profit(
        asset, strategy, gov, vault, second_profit, totalFees, totalRefunds
    )

    total_second_fees = vault.convertToShares(int(total_second_fees))
    total_second_refunds = vault.convertToShares(int(total_second_refunds))
    assert_price_per_share(vault, pricePerShare)

    time_passed = chain.pending_timestamp - timestamp
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=totalRefunds * 2,
        totalAssets=amount + first_profit + second_profit + 2 * totalRefunds,
        totalSupply=amount
        + totalRefunds
        + total_second_refunds
        - totalRefunds // (WEEK / time_passed)
        + totalFees
        + total_second_fees
        + first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT)
        - first_profit
        * (1 - performanceFee / MAX_BPS_ACCOUNTANT)
        // (WEEK / time_passed)
        + vault.convertToShares(
            int(second_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT))
        ),
    )

    increase_time_and_check_profit_buffer(chain, vault)

    assert vault.pricePerShare() / 10 ** vault.decimals() < 5.0
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=2 * totalRefunds,
        totalAssets=amount + first_profit + second_profit + 2 * totalRefunds,
        totalSupply=amount + totalFees + total_second_fees,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit + 2 * totalRefunds,
        totalAssets=amount + first_profit + second_profit + 2 * totalRefunds,
        totalSupply=amount + totalFees + total_second_fees,
    )

    assert vault.pricePerShare() / 10 ** vault.decimals() < 5.0
    assert vault.strategies(strategy).currentDebt == 0

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=vault.convertToAssets(vault.balanceOf(accountant)),
        totalAssets=vault.convertToAssets(vault.balanceOf(accountant)),
        totalSupply=totalFees + total_second_fees,
    )

    # User ends up with the initial deposit, the profit and the refunds
    assert asset.balanceOf(fish) < fish_amount + first_profit * (
        1 + refundRatio / MAX_BPS_ACCOUNTANT
    ) + second_profit * (1 + refundRatio / MAX_BPS_ACCOUNTANT)

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)
    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    assert asset.balanceOf(vault) == 0


def test_gain_fees_no_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10
    # Using only performanceFee as its easier to measure for tests
    managementFee = 0
    performanceFee = 1_000
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )

    first_profit_fees = create_and_check_profit(
        asset,
        strategy,
        gov,
        vault,
        first_profit,
        first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )
    timestamp = chain.pending_timestamp

    totalFeesShares = vault.convertToShares(first_profit_fees)
    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    assert vault.balanceOf(vault) == first_profit * (
        1 - performanceFee / MAX_BPS_ACCOUNTANT
    )
    fee_shares = first_profit * performanceFee / MAX_BPS_ACCOUNTANT
    assert vault.balanceOf(accountant) == fee_shares

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2,
    )
    assert vault.pricePerShare() / 10 ** vault.decimals() < 2.0
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount
        + first_profit * performanceFee / MAX_BPS_ACCOUNTANT
        + first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2,
    )

    assert (
        pytest.approx(vault.balanceOf(vault), rel=1e-3)
        == first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2
    )

    price_per_share_before_2nd_profit = vault.pricePerShare() / 10 ** vault.decimals()
    accountant_shares_before_2nd_profit = vault.balanceOf(accountant)
    vault_shares_before_2nd_profit = vault.balanceOf(vault)

    second_profit_fees = create_and_check_profit(
        asset,
        strategy,
        gov,
        vault,
        second_profit,
        totalFees=second_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )
    totalFeesShares += vault.convertToShares(second_profit_fees)

    # # pps doesn't change as profit goes directly to buffer and fees are damped
    assert_price_per_share(vault, price_per_share_before_2nd_profit)

    assert (
        pytest.approx(vault.balanceOf(accountant), rel=1e-4)
        == accountant_shares_before_2nd_profit
        + second_profit
        * performanceFee
        // MAX_BPS_ACCOUNTANT
        / price_per_share_before_2nd_profit
    )

    assert (
        pytest.approx(vault.balanceOf(vault), 1e-4)
        == vault_shares_before_2nd_profit
        + second_profit
        * (1 - performanceFee / MAX_BPS_ACCOUNTANT)
        / price_per_share_before_2nd_profit
    )

    time_passed = chain.pending_timestamp - timestamp

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount
        + first_profit * performanceFee / MAX_BPS_ACCOUNTANT
        + first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT)
        - first_profit
        * (1 - performanceFee / MAX_BPS_ACCOUNTANT)
        // (WEEK / time_passed)
        + vault.convertToShares(second_profit),
    )

    # We increase time and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)

    # pps is not as big as fees lower it
    price_per_share_without_fees = 3.0
    assert vault.pricePerShare() / 10 ** vault.decimals() < price_per_share_without_fees

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert vault.pricePerShare() / 10 ** vault.decimals() < price_per_share_without_fees
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount + totalFeesShares,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, vault.totalAssets() / vault.balanceOf(accountant))

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=vault.convertToAssets(vault.balanceOf(accountant)),
        totalAssets=vault.convertToAssets(vault.balanceOf(accountant)),
        totalSupply=totalFeesShares,
    )

    assert fish_amount < asset.balanceOf(fish)
    # Fish gets back profits
    assert asset.balanceOf(fish) > fish_amount + first_profit
    assert asset.balanceOf(fish) < fish_amount + first_profit + second_profit

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)
    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    assert asset.balanceOf(vault) == 0


def test_gain_fees_no_refunds_not_enough_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10
    # Using only performanceFee as its easier to measure for tests
    managementFee = 0
    first_performance_fee = 1_000
    # Huge fee that profit cannot damp
    second_performance_fee = 20_000
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        first_performance_fee,
        refundRatio,
        accountant_mint=0,
    )

    first_profit_fees = create_and_check_profit(
        asset,
        strategy,
        gov,
        vault,
        first_profit,
        first_profit * first_performance_fee / MAX_BPS_ACCOUNTANT,
    )
    timestamp = chain.pending_timestamp

    totalFeesShares = vault.convertToShares(first_profit_fees)
    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )
    assert vault.balanceOf(vault) == first_profit * (
        1 - first_performance_fee / MAX_BPS_ACCOUNTANT
    )
    fee_shares = first_profit * (first_performance_fee / MAX_BPS_ACCOUNTANT)
    assert vault.balanceOf(accountant) == fee_shares

    # Increase fees to create a huge fee
    set_fees_for_strategy(
        gov,
        strategy,
        accountant,
        managementFee,
        second_performance_fee,
        refundRatio=0,
    )

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit
        * (1 - first_performance_fee / MAX_BPS_ACCOUNTANT)
        // 2,
    )
    assert vault.pricePerShare() / 10 ** vault.decimals() < 2.0
    time_passed = chain.pending_timestamp - timestamp

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount
        + first_profit_fees
        + first_profit
        - first_profit_fees
        - (first_profit - first_profit_fees) // (WEEK / time_passed),
    )

    assert pytest.approx(vault.balanceOf(vault), rel=1e-3) == first_profit * (
        1 - first_performance_fee / MAX_BPS_ACCOUNTANT
    ) // (WEEK / time_passed)

    assert accountant.fees(strategy).performanceFee == second_performance_fee

    asset.transfer(strategy, second_profit, sender=gov)
    strategy.report(sender=gov)

    price_per_share_before_2nd_profit = vault.pricePerShare() / 10 ** vault.decimals()
    accountant_shares_before_2nd_profit = vault.balanceOf(accountant)

    tx = vault.processReport(strategy, sender=gov)
    event = list(tx.decode_logs(vault.StrategyReported))
    totalFeesShares += vault.convertToShares(event[0].totalFees)

    # pps changes as profit goes directly to buffer and fees are damped
    assert (
        vault.pricePerShare() / 10 ** vault.decimals()
        < price_per_share_before_2nd_profit
    )

    assert (
        pytest.approx(vault.balanceOf(accountant), rel=1e-4)
        == accountant_shares_before_2nd_profit
        + (second_profit * second_performance_fee // MAX_BPS_ACCOUNTANT)
        / price_per_share_before_2nd_profit
    )
    assert vault.balanceOf(vault) == 0

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount + totalFeesShares,
    )

    # We update strategy debt to 0
    add_debt_to_strategy(gov, strategy, vault, 0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount + totalFeesShares,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=vault.convertToAssets(vault.balanceOf(accountant)),
        totalAssets=vault.convertToAssets(vault.balanceOf(accountant)),
        totalSupply=totalFeesShares,
    )

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)
    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )

    assert asset.balanceOf(vault) == 0


def test_loss_no_fees_no_refunds_no_existing_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_loss = fish_amount // 20

    managementFee = 0
    performanceFee = 0
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )
    create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        first_loss * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    assert_price_per_share(vault, 0.5)
    assert vault.balanceOf(vault) == 0

    check_vault_totals(
        vault,
        totalDebt=amount - first_loss,
        totalIdle=0,
        totalAssets=amount - first_loss,
        totalSupply=amount,
    )

    # Update strategy debt to 0
    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 0.5)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount - first_loss,
        totalAssets=amount - first_loss,
        totalSupply=amount,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(fish) == fish_amount - first_loss


def test_loss_fees_no_refunds_no_existing_buffer(
    asset,
    fish_amount,
    fish,
    add_debt_to_strategy,
    gov,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_loss = fish_amount // 20

    managementFee = 10_000
    performanceFee = 0
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )

    totalFees = create_and_check_loss(strategy, gov, vault, first_loss)
    fees_shares = vault.convertToShares(totalFees)
    assert vault.pricePerShare() / 10 ** vault.decimals() < 0.5
    assert vault.balanceOf(vault) == 0

    check_vault_totals(
        vault,
        totalDebt=amount - first_loss,
        totalIdle=0,
        totalAssets=amount - first_loss,
        totalSupply=amount + fees_shares,
    )

    # Update strategy debt to 0
    add_debt_to_strategy(gov, strategy, vault, 0)

    # Fish redeems shares
    tx = vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=totalFees,
        totalAssets=totalFees,
        totalSupply=vault.balanceOf(accountant),
    )

    assert asset.balanceOf(fish) < fish_amount - first_loss

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )


def test_loss_no_fees_refunds_no_existing_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_loss = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 10_000  # 100%

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=first_loss,
    )

    totalRefunds = first_loss * refundRatio / MAX_BPS_ACCOUNTANT
    create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        totalRefunds=totalRefunds,
    )

    assert_price_per_share(vault, 1.0)
    assert vault.balanceOf(vault) == 0

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=totalRefunds,
        totalAssets=totalRefunds,
        totalSupply=amount,
    )

    assert vault.balanceOf(accountant) == 0

    # Update strategy debt to 0
    with reverts("new debt equals current debt"):
        add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=totalRefunds,
        totalAssets=totalRefunds,
        totalSupply=amount,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )
    assert asset.balanceOf(fish) == fish_amount


def test_loss_no_fees_with_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    first_loss = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 5_000

    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=2 * amount,
    )

    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT
    create_and_check_profit(asset, strategy, gov, vault, first_profit, 0, totalRefunds)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit + totalRefunds,
    )
    assert vault.balanceOf(vault) == first_profit + totalRefunds
    assert vault.balanceOf(accountant) == 0
    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit // 2 + totalRefunds // 2,
    )

    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()
    assert pricePerShare < 2.0
    assert (
        pytest.approx(vault.balanceOf(vault), rel=1e-3)
        == first_profit // 2 + totalRefunds // 2
    )

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + totalRefunds + first_profit,
        totalSupply=amount
        + totalRefunds
        - totalRefunds // 2
        + first_profit
        - first_profit // 2,
    )

    create_and_check_loss(strategy, gov, vault, first_loss, totalRefunds)

    assert_price_per_share(vault, pricePerShare)

    # need to account for the extra time that has passed for the loss tx
    time_passed = chain.pending_timestamp - timestamp

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit - first_loss,
        totalIdle=totalRefunds * 2,
        totalAssets=amount + first_profit - first_loss + 2 * totalRefunds,
        totalSupply=amount
        + totalRefunds
        + vault.convertToShares(int(totalRefunds))
        - totalRefunds // (WEEK / time_passed)
        + first_profit
        - first_profit // (WEEK / time_passed)
        - vault.convertToShares(first_loss),
    )

    # The full profit from the first report should be fully unlocked in the same time
    # period as initially set
    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK // 2)

    assert_price_per_share(vault, 2.0)

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit - first_loss,
        totalIdle=totalRefunds * 2,
        totalAssets=amount + first_profit - first_loss + totalRefunds * 2,
        totalSupply=amount,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit - first_loss + totalRefunds * 2,
        totalAssets=amount + first_profit - first_loss + totalRefunds * 2,
        totalSupply=amount,
    )
    assert_price_per_share(vault, 2.0)
    assert vault.strategies(strategy).currentDebt == 0

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault, totalDebt=0, totalIdle=0, totalAssets=0, totalSupply=0
    )
    assert asset.balanceOf(vault) == 0

    # User ends up with the initial deposit, the profit and the refunds
    assert (
        asset.balanceOf(fish)
        == fish_amount
        + first_profit
        + first_profit * refundRatio / MAX_BPS_ACCOUNTANT
        + first_loss * refundRatio / MAX_BPS_ACCOUNTANT
        - first_loss
    )

    # Accountant redeems shares
    with reverts("no shares to redeem"):
        vault.redeem(
            vault.balanceOf(accountant), accountant, accountant, sender=accountant
        )


def test_loss_no_fees_no_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    first_loss = fish_amount // 50

    managementFee = 0
    performanceFee = 0
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )
    create_and_check_profit(
        asset,
        strategy,
        gov,
        vault,
        first_profit,
        first_profit * performanceFee / MAX_BPS_ACCOUNTANT,
    )
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2,
    )

    assert vault.pricePerShare() / 10 ** vault.decimals() < 2.0
    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()

    assert pytest.approx(vault.balanceOf(vault), rel=1e-3) == first_profit // 2

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount
        + first_profit * performanceFee / MAX_BPS_ACCOUNTANT
        + first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2,
    )

    # We create a virtual loss that doesn't change pps as its taken care by profit buffer
    create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        first_loss * performanceFee / MAX_BPS_ACCOUNTANT,
    )
    assert_price_per_share(vault, pricePerShare)
    assert pytest.approx(
        vault.balanceOf(vault), rel=1e-3
    ) == first_profit // 2 - vault.convertToShares(first_loss)

    time_passed = chain.pending_timestamp - timestamp

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit - first_loss,
        totalIdle=0,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount
        + first_profit
        - first_profit // (WEEK / time_passed)
        - vault.convertToShares(first_loss),
    )

    # We increase time and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)

    assert_price_per_share(vault, (amount + first_profit - first_loss) / amount)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, (amount + first_profit - first_loss) / amount)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit - first_loss,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(fish) == fish_amount + first_profit - first_loss
    assert asset.balanceOf(fish) > fish_amount


def test_loss_fees_no_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_accountant,
    set_fees_for_strategy,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    first_loss = fish_amount // 50

    managementFee = 500
    performanceFee = 0
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )
    total_profit_fees = create_and_check_profit(
        asset, strategy, gov, vault, first_profit, totalFees=0, by_pass_fees=True
    )
    total_profit_fees = vault.convertToShares(total_profit_fees)
    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )
    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit * (1 - performanceFee / MAX_BPS_ACCOUNTANT) // 2,
    )

    assert vault.pricePerShare() / 10 ** vault.decimals() < 2.0
    pricePerShare = vault.totalAssets() / (amount + first_profit - first_profit // 2)

    assert pytest.approx(vault.balanceOf(vault), rel=1e-3) == first_profit // 2

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount
        + total_profit_fees
        + (first_profit - total_profit_fees) // 2,
    )

    # We create a virtual loss that doesn't change pps as its taken care by profit buffer
    total_loss_fees = create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        first_loss * performanceFee / MAX_BPS_ACCOUNTANT,
    )

    total_loss_fees = vault.convertToShares(total_loss_fees)
    assert total_loss_fees > 0
    # pps is not affected by fees
    assert (
        pytest.approx(pricePerShare, rel=1e-3)
        == vault.pricePerShare() / 10 ** vault.decimals()
    )
    assert vault.balanceOf(vault) < first_profit // 2

    assert vault.totalAssets() == amount + first_profit - first_loss
    assert vault.totalSupply() > amount
    assert (
        vault.totalSupply() < amount + first_profit / 2
    )  # Because we have burned shares

    # We increase time and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0

    # pps is slightly lower due to fees
    assert (
        vault.pricePerShare() / 10 ** vault.decimals()
        < (amount + first_profit - first_loss) / amount
    )

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit - first_loss,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount + total_profit_fees + total_loss_fees,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=vault.convertToAssets(vault.balanceOf(accountant)),
        totalAssets=vault.convertToAssets(vault.balanceOf(accountant)),
        totalSupply=total_loss_fees + total_profit_fees,
    )
    assert vault.totalDebt() == 0
    assert vault.totalSupply() == vault.balanceOf(accountant)
    assert asset.balanceOf(vault) == vault.convertToAssets(vault.balanceOf(accountant))

    assert asset.balanceOf(fish) < fish_amount + first_profit - first_loss
    assert asset.balanceOf(fish) > fish_amount

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )


def test_loss_no_fees_no_refunds_with_not_enough_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 20
    first_loss = fish_amount // 10

    managementFee = 0
    performanceFee = 0
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )

    create_and_check_profit(asset, strategy, gov, vault, first_profit)
    assert_price_per_share(vault, 1.0)
    assert vault.balanceOf(vault) == first_profit

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit // 2,
    )

    assert vault.pricePerShare() / 10 ** vault.decimals() < 2.0
    assert pytest.approx(vault.balanceOf(vault), rel=1e-3) == first_profit // 2

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit // 2,
    )

    # We create a virtual loss
    create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        0,
    )
    assert_price_per_share(vault, (amount + first_profit - first_loss) / amount)
    assert vault.balanceOf(vault) == 0

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit - first_loss,
        totalIdle=0,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount,
    )

    # We increase time and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)

    assert_price_per_share(vault, (amount + first_profit - first_loss) / amount)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, (amount + first_profit - first_loss) / amount)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit - first_loss,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount,
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(fish) == fish_amount + first_profit - first_loss
    assert asset.balanceOf(fish) < fish_amount


def test_loss_fees_no_refunds_with_not_enough_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_accountant,
    set_fees_for_strategy,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 20
    first_loss = fish_amount // 10

    managementFee = 500
    performanceFee = 0
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=0,
    )

    total_profit_fees = create_and_check_profit(
        asset, strategy, gov, vault, first_profit, 0, by_pass_fees=True
    )

    assert_price_per_share(vault, 1.0)
    assert vault.balanceOf(vault) == first_profit - total_profit_fees

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=first_profit // 2,
    )

    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()
    assert vault.pricePerShare() / 10 ** vault.decimals() <= pricePerShare
    assert pytest.approx(vault.balanceOf(vault), rel=1e-3) == first_profit // 2

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount
        + total_profit_fees
        + (first_profit - total_profit_fees) // 2,
    )

    # We create a virtual loss
    total_loss_fees = create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        0,
    )

    assert (
        vault.pricePerShare() / 10 ** vault.decimals()
        < (amount + first_profit - first_loss) / amount
    )

    assert vault.balanceOf(vault) == 0
    assert total_loss_fees > 0

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit - first_loss,
        totalIdle=0,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount + vault.balanceOf(accountant),
    )

    assert pytest.approx(vault.pricePerShare() / 10 ** vault.decimals(), rel=1e-3) == (
        amount + first_profit - first_loss
    ) / (amount + total_loss_fees / pricePerShare + total_profit_fees)
    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()

    # We increase time and update strategy debt to 0
    increase_time_and_check_profit_buffer(chain, vault)

    assert vault.balanceOf(vault) == 0
    assert_price_per_share(vault, pricePerShare)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, pricePerShare)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit - first_loss,
        totalAssets=amount + first_profit - first_loss,
        totalSupply=amount + vault.balanceOf(accountant),
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=vault.convertToAssets(vault.balanceOf(accountant)),
        totalAssets=vault.convertToAssets(vault.balanceOf(accountant)),
        totalSupply=vault.balanceOf(accountant),
    )

    assert asset.balanceOf(fish) < fish_amount
    assert asset.balanceOf(fish) < fish_amount + first_profit - first_loss

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )


def test_loss_fees_refunds(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_accountant,
    set_fees_for_strategy,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_loss = fish_amount // 10

    managementFee = 100
    performanceFee = 0
    refundRatio = 10_000  # Losses are covered 100%

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=first_loss,
    )

    # let vault take its 1% fee
    chain.mine(timestamp=chain.pending_timestamp + 31_556_952)

    totalRefunds = first_loss * refundRatio / MAX_BPS_ACCOUNTANT
    total_loss_fees = create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        totalRefunds=totalRefunds,
    )

    assert total_loss_fees > 0
    assert vault.balanceOf(vault) == 0

    loss_fees_shares = vault.convertToShares(total_loss_fees)
    check_vault_totals(
        vault,
        totalDebt=amount - first_loss,
        totalIdle=totalRefunds,
        totalAssets=totalRefunds,
        totalSupply=amount + loss_fees_shares,
    )

    # 1% down due to fee
    assert_price_per_share(vault, 0.99)

    assert (
        pytest.approx(vault.convertToAssets(vault.balanceOf(accountant)), abs=1)
        == total_loss_fees
    )

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 0.99)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=total_loss_fees,
        totalAssets=total_loss_fees,
        totalSupply=loss_fees_shares,
    )

    assert (
        pytest.approx(asset.balanceOf(fish), rel=1e-4) == fish_amount - total_loss_fees
    )

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )


def test_loss_fees_refunds_with_buffer(
    create_vault,
    asset,
    fish_amount,
    create_lossy_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_accountant,
    set_fees_for_strategy,
    initial_set_up_lossy,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    first_loss = fish_amount // 10

    managementFee = 500
    performanceFee = 0
    refundRatio = 10_000  # Losses are covered 100%

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
        managementFee,
        performanceFee,
        refundRatio,
        accountant_mint=2 * amount,
    )
    totalRefunds = first_profit * refundRatio / MAX_BPS_ACCOUNTANT
    totalFees = create_and_check_profit(
        asset, strategy, gov, vault, first_profit, 0, totalRefunds, by_pass_fees=True
    )
    totalFees = vault.convertToShares(totalFees)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount + first_profit + totalRefunds,
    )
    assert pytest.approx(vault.balanceOf(vault), 1e-4) == totalRefunds + (
        first_profit - totalFees
    )
    assert vault.balanceOf(accountant) == totalFees

    # We increase time after profit has been released and update strategy debt to 0
    increase_time_and_check_profit_buffer(
        chain,
        vault,
        secs=WEEK // 2,
        expected_buffer=(first_profit - totalFees) // 2 + totalRefunds // 2,
    )

    pricePerShare = vault.pricePerShare() / 10 ** vault.decimals()
    assert pricePerShare < 2.0
    assert (
        pytest.approx(vault.balanceOf(vault), rel=1e-3)
        == first_profit // 2 + totalRefunds // 2
    )
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=totalRefunds,
        totalAssets=amount + first_profit + totalRefunds,
        totalSupply=amount
        + (first_profit - totalFees) // 2
        + totalRefunds
        - totalRefunds // 2
        + totalFees,
    )

    total_second_refunds = first_loss * refundRatio / MAX_BPS_ACCOUNTANT
    total_second_fees = create_and_check_loss(
        strategy,
        gov,
        vault,
        first_loss,
        totalRefunds=total_second_refunds,
    )
    total_second_fees = vault.convertToShares(total_second_fees)

    assert total_second_fees > 0

    increase_time_and_check_profit_buffer(chain, vault)

    assert vault.pricePerShare() / 10 ** vault.decimals() < 3.0
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit - first_loss,
        totalIdle=totalRefunds + total_second_refunds,
        totalAssets=amount
        + first_profit
        - first_loss
        + totalRefunds
        + total_second_refunds,
        totalSupply=amount + totalFees + total_second_fees,
    )

    add_debt_to_strategy(gov, strategy, vault, 0)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount
        + first_profit
        - first_loss
        + totalRefunds
        + total_second_refunds,
        totalAssets=amount
        + first_profit
        - first_loss
        + totalRefunds
        + total_second_refunds,
        totalSupply=amount + totalFees + total_second_fees,
    )
    assert vault.pricePerShare() / 10 ** vault.decimals() < 3.0
    assert vault.strategies(strategy).currentDebt == 0

    # Fish redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert pytest.approx(vault.totalSupply(), 1e-4) == totalFees + total_second_fees

    assert asset.balanceOf(fish) < fish_amount + first_profit * (
        1 + refundRatio / MAX_BPS_ACCOUNTANT
    ) + first_loss * (1 + refundRatio / MAX_BPS_ACCOUNTANT)
    assert asset.balanceOf(fish) > fish_amount

    # Accountant redeems shares
    vault.redeem(vault.balanceOf(accountant), accountant, accountant, sender=accountant)

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )


def test_accountant_and_protocolFees_doesnt_change_pps(
    create_vault,
    asset,
    fish_amount,
    create_strategy,
    user_deposit,
    fish,
    add_strategy_to_vault,
    add_debt_to_strategy,
    gov,
    airdrop_asset,
    deploy_flexible_accountant,
    set_fees_for_strategy,
    initial_set_up,
    vault_factory,
    set_factory_fee_config,
    bunny,
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    # Using only managementFee as its easier to measure comparision
    managementFee = 25
    performanceFee = 0
    refundRatio = 0
    protocol_recipient = bunny

    # set fees
    set_factory_fee_config(managementFee, protocol_recipient)

    # Deposit assets to vault and get strategy ready. Management fee == 0 initially
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )

    # skip the time needed for the protocol to assess fees
    increase_time_and_check_profit_buffer(chain, vault)

    starting_pps = vault.pricePerShare()

    # process report with first profit
    totalFees = create_and_check_profit(
        asset, strategy, gov, vault, first_profit, 0, 0, True
    )

    # assure both accounts got payed fees and the PPS stayed exactly the same
    assert vault.balanceOf(accountant.address) != 0
    assert vault.balanceOf(protocol_recipient) != 0
    assert vault.pricePerShare() == starting_pps

    # send all fees collected out
    vault.transfer(gov, vault.balanceOf(protocol_recipient), sender=protocol_recipient)
    vault.transfer(gov, vault.balanceOf(accountant.address), sender=accountant)

    assert vault.balanceOf(protocol_recipient) == 0
    assert vault.balanceOf(accountant.address) == 0

    # skip the time needed for the protocol to assess fees
    increase_time_and_check_profit_buffer(chain, vault)

    starting_pps = vault.pricePerShare()

    totalFees = create_and_check_profit(
        asset, strategy, gov, vault, first_profit, 0, 0, True
    )

    assert vault.balanceOf(accountant.address) != 0
    assert vault.balanceOf(protocol_recipient) != 0
    assert vault.pricePerShare() == starting_pps


def test_increase_profit_max_period__no_change(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)

    create_and_check_profit(asset, strategy, gov, vault, first_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 2, expected_buffer=first_profit // 2
    )

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(WEEK * 2, sender=gov)

    time_passed = chain.pending_timestamp - timestamp
    # assure the all the amounts is what is originally would have been
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit - first_profit // (WEEK / time_passed),
    )

    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK // 2)

    assert_price_per_share(vault, 2.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 2.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit


def test_decrease_profit_max_period__no_change(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)

    create_and_check_profit(asset, strategy, gov, vault, first_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 2, expected_buffer=first_profit // 2
    )

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(WEEK // 2, sender=gov)

    time_passed = chain.pending_timestamp - timestamp
    # assure the all the amounts is what is originally would have been
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit - first_profit // (WEEK / time_passed),
    )

    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK // 2)

    assert_price_per_share(vault, 2.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 2.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit


def test_increase_profit_max_period__next_report_works(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)

    create_and_check_profit(asset, strategy, gov, vault, first_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 2, expected_buffer=first_profit // 2
    )

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(WEEK * 2, sender=gov)

    time_passed = chain.pending_timestamp - timestamp
    # assure the all the amounts is what is originally would have been
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit - first_profit // (WEEK / time_passed),
    )

    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK // 2)

    assert_price_per_share(vault, 2.0)

    create_and_check_profit(asset, strategy, gov, vault, second_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 2.0)
    # only have the amount of shares are issued due to pps = 2.0
    expected_new_shares = second_profit // 2
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount + expected_new_shares,
    )

    # increase by a full week which is now only half the profit unlock time
    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK, expected_buffer=expected_new_shares // 2
    )

    time_passed = chain.pending_timestamp - timestamp

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount
        + expected_new_shares
        - expected_new_shares // (WEEK * 2 / time_passed),
    )

    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK)

    assert_price_per_share(vault, 3.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 3.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit + second_profit


def test_decrease_profit_max_period__next_report_works(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10
    second_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)

    create_and_check_profit(asset, strategy, gov, vault, first_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 2, expected_buffer=first_profit // 2
    )

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(WEEK // 2, sender=gov)

    time_passed = chain.pending_timestamp - timestamp
    # assure the all the amounts is what is originally would have been
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit - first_profit // (WEEK / time_passed),
    )

    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK // 2)

    assert_price_per_share(vault, 2.0)

    create_and_check_profit(asset, strategy, gov, vault, second_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 2.0)
    # only have the amount of shares are issued due to pps = 2.0
    expected_new_shares = second_profit // 2
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount + expected_new_shares,
    )

    # increase by a quarter week which is now half the profit unlock time
    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 4, expected_buffer=expected_new_shares // 2
    )

    time_passed = chain.pending_timestamp - timestamp

    check_vault_totals(
        vault,
        totalDebt=amount + first_profit + second_profit,
        totalIdle=0,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount
        + expected_new_shares
        - expected_new_shares // (WEEK // 2 / time_passed),
    )

    increase_time_and_check_profit_buffer(chain, vault, secs=WEEK // 4)

    assert_price_per_share(vault, 3.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 3.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit + second_profit,
        totalAssets=amount + first_profit + second_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit + second_profit


def test_set_profit_max_period_to_zero__resets_rates(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)

    create_and_check_profit(asset, strategy, gov, vault, first_profit)
    timestamp = chain.pending_timestamp

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + first_profit,
    )

    increase_time_and_check_profit_buffer(
        chain, vault, secs=WEEK // 2, expected_buffer=first_profit // 2
    )

    assert vault.profitMaxUnlockTime() != 0
    assert vault.balanceOf(vault.address) != 0
    assert vault.fullProfitUnlockDate() != 0
    assert vault.profitUnlockingRate() != 0

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(0, sender=gov)

    assert vault.profitMaxUnlockTime() == 0
    assert vault.balanceOf(vault.address) == 0
    assert vault.fullProfitUnlockDate() == 0
    assert vault.profitUnlockingRate() == 0

    # All profits should have been unlocked
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    assert_price_per_share(vault, 2.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 2.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit


def test_set_profit_max_period_to_zero__doesnt_lock(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    vault, strategy, _ = initial_set_up(asset, gov, amount, fish)

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(0, sender=gov)

    assert vault.profitMaxUnlockTime() == 0
    assert vault.balanceOf(vault.address) == 0
    assert vault.fullProfitUnlockDate() == 0
    assert vault.profitUnlockingRate() == 0

    create_and_check_profit(asset, strategy, gov, vault, first_profit)

    # All profits should have been unlocked
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    assert_price_per_share(vault, 2.0)

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert_price_per_share(vault, 2.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount + first_profit


def test_set_profit_max_period_to_zero__with_fees_doesnt_lock(
    asset, fish_amount, fish, initial_set_up, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_profit = fish_amount // 10

    # Using only performanceFee as its easier to measure for tests
    managementFee = 0
    performanceFee = 1_000
    refundRatio = 0

    # Deposit assets to vault and get strategy ready
    vault, strategy, accountant = initial_set_up(
        asset, gov, amount, fish, managementFee, performanceFee, refundRatio
    )

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(0, sender=gov)

    assert vault.profitMaxUnlockTime() == 0
    assert vault.balanceOf(vault.address) == 0
    assert vault.fullProfitUnlockDate() == 0
    assert vault.profitUnlockingRate() == 0

    expected_fees_shares = first_profit * performanceFee / MAX_BPS_ACCOUNTANT
    first_price_per_share = vault.pricePerShare()

    expected_fee_amount = (
        expected_fees_shares
        * (amount + first_profit)
        // (amount + expected_fees_shares)
    )

    # Fees will immediately unlock as well when not locking.
    create_and_check_profit(
        asset, strategy, gov, vault, first_profit, totalFees=expected_fee_amount
    )

    # All profits should have been unlocked
    check_vault_totals(
        vault,
        totalDebt=amount + first_profit,
        totalIdle=0,
        totalAssets=amount + first_profit,
        totalSupply=amount + expected_fees_shares,
    )

    pricePerShare = vault.pricePerShare()
    assert pricePerShare > first_price_per_share

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert vault.pricePerShare() == pricePerShare
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount + first_profit,
        totalAssets=amount + first_profit,
        totalSupply=amount + expected_fees_shares,
    )

    increase_time_and_check_profit_buffer(
        chain=chain, vault=vault, secs=DAY, expected_buffer=0
    )

    assert vault.pricePerShare() == pricePerShare

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert vault.pricePerShare() == pricePerShare

    vault.redeem(
        vault.balanceOf(accountant.address), accountant, accountant, sender=accountant
    )

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert vault.pricePerShare() == first_price_per_share


def test_set_profit_max_period_to_zero___report_loss(
    asset, fish_amount, fish, initial_set_up_lossy, gov, add_debt_to_strategy
):
    amount = fish_amount // 10
    first_loss = amount // 2

    vault, strategy, _ = initial_set_up_lossy(
        asset,
        gov,
        amount,
        fish,
    )

    # update profit max unlock time
    vault.setProfitMaxUnlockTime(0, sender=gov)

    assert vault.profitMaxUnlockTime() == 0
    assert vault.balanceOf(vault.address) == 0
    assert vault.fullProfitUnlockDate() == 0
    assert vault.profitUnlockingRate() == 0

    create_and_check_loss(strategy, gov, vault, first_loss)

    # All profits should have been unlocked
    check_vault_totals(
        vault,
        totalDebt=amount - first_loss,
        totalIdle=0,
        totalAssets=amount - first_loss,
        totalSupply=amount,
    )

    assert vault.pricePerShare() / 10 ** vault.decimals() <= 0.5

    add_debt_to_strategy(gov, strategy, vault, 0)

    assert vault.strategies(strategy).currentDebt == 0
    assert vault.pricePerShare() / 10 ** vault.decimals() <= 0.5

    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=amount - first_loss,
        totalAssets=amount - first_loss,
        totalSupply=amount,
    )

    # User redeems shares
    vault.redeem(vault.balanceOf(fish), fish, fish, sender=fish)

    assert_price_per_share(vault, 1.0)
    check_vault_totals(
        vault,
        totalDebt=0,
        totalIdle=0,
        totalAssets=0,
        totalSupply=0,
    )

    assert asset.balanceOf(vault) == 0
    assert asset.balanceOf(fish) == fish_amount - first_loss
