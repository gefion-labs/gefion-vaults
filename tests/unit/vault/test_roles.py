import ape
from utils import checks
from utils.constants import MAX_INT, ROLES, ZERO_ADDRESS


def test_set_role(gov, fish, asset, create_vault):
    vault = create_vault(asset)
    vault.setRole(fish.address, ROLES.DEBT_MANAGER, sender=gov)

    with ape.reverts():
        vault.setRole(fish.address, ROLES.DEBT_MANAGER, sender=fish)

    with ape.reverts():
        vault.setRole(fish.address, 100, sender=fish)


def test_transfers_roleManager(vault, gov, strategist):
    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == ZERO_ADDRESS

    vault.transferRoleManager(strategist, sender=gov)

    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == strategist

    tx = vault.acceptRoleManager(sender=strategist)
    event = list(tx.decode_logs(vault.UpdateRoleManager))
    assert len(event) == 1
    assert event[0].roleManager == strategist

    assert vault.roleManager() == strategist
    assert vault.futureRoleManager() == ZERO_ADDRESS


def test_gov_transfers_roleManager__gov_cant_accept(vault, gov, strategist):
    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == ZERO_ADDRESS

    vault.transferRoleManager(strategist, sender=gov)

    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == strategist

    with ape.reverts():
        vault.acceptRoleManager(sender=gov)

    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == strategist


def test_random_transfers_roleManager__reverts(vault, gov, strategist):
    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == ZERO_ADDRESS

    with ape.reverts():
        vault.transferRoleManager(strategist, sender=strategist)

    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == ZERO_ADDRESS


def test_gov_transfers_roleManager__can_change_future_manager(
    vault, gov, bunny, strategist
):
    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == ZERO_ADDRESS

    vault.transferRoleManager(strategist, sender=gov)

    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == strategist

    vault.transferRoleManager(bunny, sender=gov)

    assert vault.roleManager() == gov
    assert vault.futureRoleManager() == bunny

    with ape.reverts():
        vault.acceptRoleManager(sender=strategist)

    tx = vault.acceptRoleManager(sender=bunny)
    event = list(tx.decode_logs(vault.UpdateRoleManager))
    assert len(event) == 1
    assert event[0].roleManager == bunny

    assert vault.roleManager() == bunny
    assert vault.futureRoleManager() == ZERO_ADDRESS
