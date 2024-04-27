import ape
from ape import project, reverts
from utils.constants import WEEK


def test_new_vault_with_different_salt(gov, asset, bunny, fish, vault_factory):
    assert vault_factory.name() == "Vault Factory test"

    tx = vault_factory.deployNewVault(
        asset.address,
        "first_vault",
        "fv",
        bunny.address,
        WEEK,
        sender=gov,
    )
    event = list(tx.decode_logs(vault_factory.NewVault))
    new_vault = project.Vault.at(event[0].vaultAddress)
    assert new_vault.name() == "first_vault"
    assert new_vault.roleManager() == bunny.address

    tx = vault_factory.deployNewVault(
        asset.address,
        "second_vault",
        "sv",
        fish.address,
        WEEK,
        sender=gov,
    )
    event = list(tx.decode_logs(vault_factory.NewVault))
    new_vault = project.Vault.at(event[0].vaultAddress)
    assert new_vault.name() == "second_vault"
    assert new_vault.roleManager() == fish.address


def test_new_vault_same_name_asset_and_symbol_different_sender(
    gov, asset, bunny, vault_factory
):
    tx = vault_factory.deployNewVault(
        asset.address,
        "first_vault",
        "fv",
        bunny.address,
        WEEK,
        sender=gov,
    )
    event = list(tx.decode_logs(vault_factory.NewVault))
    new_vault = project.Vault.at(event[0].vaultAddress)
    assert new_vault.name() == "first_vault"
    assert new_vault.roleManager() == bunny.address

    vault_factory.deployNewVault(
        asset.address,
        "first_vault",
        "fv",
        bunny.address,
        WEEK,
        sender=bunny,
    )
    event = list(tx.decode_logs(vault_factory.NewVault))
    new_vault = project.Vault.at(event[0].vaultAddress)
    assert new_vault.name() == "first_vault"
    assert new_vault.roleManager() == bunny.address


def test_new_vault_same_sender_name_asset_and_symbol__reverts(
    gov, asset, bunny, vault_factory
):
    tx = vault_factory.deployNewVault(
        asset.address,
        "first_vault",
        "fv",
        bunny.address,
        WEEK,
        sender=gov,
    )
    event = list(tx.decode_logs(vault_factory.NewVault))
    new_vault = project.Vault.at(event[0].vaultAddress)
    assert new_vault.name() == "first_vault"
    assert new_vault.roleManager() == bunny.address

    with ape.reverts():
        vault_factory.deployNewVault(
            asset.address,
            "first_vault",
            "fv",
            bunny.address,
            WEEK,
            sender=gov,
        )


def test__shutdownFactory(gov, asset, bunny, vault_factory):
    assert vault_factory.shutdown() == False

    tx = vault_factory.shutdownFactory(sender=gov)

    event = list(tx.decode_logs(vault_factory.FactoryShutdown))

    assert len(event) == 1

    assert vault_factory.shutdown() == True

    with ape.reverts("shutdown"):
        vault_factory.deployNewVault(
            asset.address,
            "first_vault",
            "fv",
            bunny.address,
            WEEK,
            sender=gov,
        )


def test__shutdownFactory__reverts(gov, asset, bunny, vault_factory):
    assert vault_factory.shutdown() == False

    with ape.reverts("not governance"):
        vault_factory.shutdownFactory(sender=bunny)


def test_reinitialize_vault__reverst(gov, asset, bunny, vault_factory):
    # Can't initialize the original
    original = project.Vault.at(vault_factory.vaultOriginal())

    with ape.reverts("initialized"):
        original.initialize(
            asset.address,
            "first_vault",
            "fv",
            bunny.address,
            WEEK,
            sender=gov,
        )

    tx = vault_factory.deployNewVault(
        asset.address,
        "first_vault",
        "fv",
        bunny.address,
        WEEK,
        sender=gov,
    )
    event = list(tx.decode_logs(vault_factory.NewVault))
    new_vault = project.Vault.at(event[0].vaultAddress)
    assert new_vault.name() == "first_vault"
    assert new_vault.roleManager() == bunny.address

    # Can't reinitialze a new vault.
    with ape.reverts("initialized"):
        new_vault.initialize(
            asset.address,
            "first_vault",
            "fv",
            bunny.address,
            WEEK,
            sender=gov,
        )
