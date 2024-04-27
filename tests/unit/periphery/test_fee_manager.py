import ape
import pytest
from utils.constants import ZERO_ADDRESS


def test_deploy_accountant(project, gov, asset):
    accountant = gov.deploy(project.Accountant, asset)

    assert accountant.feeManager() == gov


def test_distribute(gov, bunny, vault, deploy_accountant):
    accountant = deploy_accountant(vault)
    with ape.reverts("not fee manager"):
        accountant.distribute(vault.address, sender=bunny)

    rewards = vault.balanceOf(gov)
    # give fee manager vault shares
    vault.transfer(accountant.address, rewards, sender=gov)
    assert vault.balanceOf(accountant) == rewards

    tx = accountant.distribute(vault.address, sender=gov)
    event = list(tx.decode_logs(accountant.DistributeRewards))

    assert len(event) == 1
    assert event[0].rewards == rewards

    assert vault.balanceOf(gov) == rewards


@pytest.mark.parametrize("performanceFee", [0, 2500, 5000])
def test_set_performance_fee__with_valid_performance_fee(
    gov, vault, deploy_accountant, performanceFee
):
    accountant = deploy_accountant(vault)
    tx = accountant.setPerformanceFee(vault.address, performanceFee, sender=gov)
    event = list(tx.decode_logs(accountant.UpdatePerformanceFee))

    assert len(event) == 1
    assert event[0].performanceFee == performanceFee

    assert accountant.fees(vault).performanceFee == performanceFee


def test_set_performance_fee_with_invalid_performance_fee_reverts(
    gov, bunny, vault, deploy_accountant
):
    accountant = deploy_accountant(vault)
    valid_performance_fee = 5000
    invalid_performance_fee = 5001

    with ape.reverts("not fee manager"):
        accountant.setPerformanceFee(
            vault.address, valid_performance_fee, sender=bunny
        )

    with ape.reverts("exceeds performance fee threshold"):
        accountant.setPerformanceFee(
            vault.address, invalid_performance_fee, sender=gov
        )


@pytest.mark.parametrize("managementFee", [0, 5000, 10000])
def test_management_fee__with_valid_management_fee(
    gov, vault, deploy_accountant, managementFee
):
    accountant = deploy_accountant(vault)
    tx = accountant.setManagementFee(vault.address, managementFee, sender=gov)
    event = list(tx.decode_logs(accountant.UpdateManagementFee))

    assert len(event) == 1
    assert event[0].managementFee == managementFee

    assert accountant.fees(vault).managementFee == managementFee


def test_management_fee__with_invalid_management_fee_reverts(
    gov, bunny, vault, deploy_accountant
):
    accountant = deploy_accountant(vault)
    valid_management_fee = 10000
    invalid_management_fee = 10001

    with ape.reverts("not fee manager"):
        accountant.setManagementFee(vault.address, valid_management_fee, sender=bunny)

    with ape.reverts("exceeds management fee threshold"):
        accountant.setManagementFee(vault.address, invalid_management_fee, sender=gov)


def test_commit_fee_manager__with_new_fee_manager(gov, bunny, vault, deploy_accountant):
    accountant = deploy_accountant(vault)
    with ape.reverts("not fee manager"):
        accountant.commitFeeManager(bunny.address, sender=bunny)

    tx = accountant.commitFeeManager(bunny.address, sender=gov)
    event = list(tx.decode_logs(accountant.CommitFeeManager))

    assert len(event) == 1
    assert event[0].feeManager == bunny.address

    assert accountant.futureFeeManager() == bunny.address


def test_apply_fee_manager__with_new_fee_manager(gov, bunny, vault, deploy_accountant):
    accountant = deploy_accountant(vault)
    accountant.commitFeeManager(ZERO_ADDRESS, sender=gov)

    with ape.reverts("not fee manager"):
        accountant.applyFeeManager(sender=bunny)

    with ape.reverts("future fee manager != zero address"):
        accountant.applyFeeManager(sender=gov)

    accountant.commitFeeManager(bunny.address, sender=gov)

    tx = accountant.applyFeeManager(sender=gov)
    event = list(tx.decode_logs(accountant.ApplyFeeManager))

    assert len(event) == 1
    assert event[0].feeManager == bunny.address

    assert accountant.feeManager() == bunny.address


@pytest.mark.parametrize("refundRatio", [0, 5_000, 10_000])
def test_set_refund_ratio(gov, vault, deploy_accountant, refundRatio):
    accountant = deploy_accountant(vault)
    tx = accountant.setRefundRatio(vault.address, refundRatio, sender=gov)
    event = list(tx.decode_logs(accountant.UpdateRefundRatio))

    assert len(event) == 1
    assert event[0].refundRatio == refundRatio

    assert accountant.refundRatios(vault) == refundRatio
