import ape
from ape import chain
from utils.constants import ZERO_ADDRESS


def test__setProtocolFeeRecipient(gov, vault_factory):
    tx = vault_factory.setProtocolFeeRecipient(gov.address, sender=gov)

    event = list(tx.decode_logs(vault_factory.UpdateProtocolFeeRecipient))
    assert event[0].oldFeeRecipient == ZERO_ADDRESS
    assert event[0].newFeeRecipient == gov.address

    assert vault_factory.protocolFeeConfig().feeRecipient == gov.address


def test__setProtocolFeeRecipient__zero_address__reverts(gov, vault_factory):
    with ape.reverts("zero address"):
        vault_factory.setProtocolFeeRecipient(ZERO_ADDRESS, sender=gov)


def test__set_protocolFees(gov, vault_factory):
    assert vault_factory.protocolFeeConfig().feeBps == 0

    # Need to set the fee recipient first
    vault_factory.setProtocolFeeRecipient(gov.address, sender=gov)

    tx = vault_factory.setProtocolFeeBps(20, sender=gov)

    event = list(tx.decode_logs(vault_factory.UpdateProtocolFeeBps))
    assert event[0].oldFeeBps == 0
    assert event[0].newFeeBps == 20

    assert vault_factory.protocolFeeConfig().feeBps == 20


def test__set_customProtocolFee(gov, vault_factory, create_vault, asset):
    # Set the default protocol fee recipient
    vault_factory.setProtocolFeeRecipient(gov.address, sender=gov)

    assert vault_factory.protocolFeeConfig().feeRecipient == gov.address
    assert vault_factory.protocolFeeConfig().feeBps == 0

    vault = create_vault(asset)

    # Make sure its currently set to the default settings.
    assert (
        vault_factory.protocolFeeConfig(sender=vault.address).feeRecipient
        == gov.address
    )
    assert vault_factory.protocolFeeConfig(sender=vault.address).feeBps == 0
    assert vault_factory.protocolFeeConfig(vault.address).feeRecipient == gov.address
    assert vault_factory.protocolFeeConfig(vault.address).feeBps == 0

    new_fee = int(20)
    # Set custom fee for new vault.
    tx = vault_factory.setCustomProtocolFeeBps(vault.address, new_fee, sender=gov)

    event = list(tx.decode_logs(vault_factory.UpdateCustomProtocolFee))

    assert len(event) == 1
    assert event[0].vault == vault.address
    assert event[0].newCustomProtocolFee == new_fee

    assert vault_factory.useCustomProtocolFee(vault.address) == True
    assert vault_factory.customProtocolFee(vault.address) == new_fee

    # Should now be different than default
    assert (
        vault_factory.protocolFeeConfig(sender=vault.address).feeRecipient
        == gov.address
    )
    assert vault_factory.protocolFeeConfig(sender=vault.address).feeBps == new_fee
    assert vault_factory.protocolFeeConfig(vault.address).feeRecipient == gov.address
    assert vault_factory.protocolFeeConfig(vault.address).feeBps == new_fee

    # Make sure the default is not changed.
    assert vault_factory.protocolFeeConfig().feeRecipient == gov.address
    assert vault_factory.protocolFeeConfig().feeBps == 0


def test__removeCustomProtocolFee(gov, vault_factory, create_vault, asset):
    # Set the default protocol fee recipient
    vault_factory.setProtocolFeeRecipient(gov.address, sender=gov)

    generic_fee = int(8)
    vault_factory.setProtocolFeeBps(generic_fee, sender=gov)

    vault = create_vault(asset)

    new_fee = int(20)
    # Set custom fee for new vault.
    tx = vault_factory.setCustomProtocolFeeBps(vault.address, new_fee, sender=gov)

    event = list(tx.decode_logs(vault_factory.UpdateCustomProtocolFee))

    assert len(event) == 1
    assert event[0].vault == vault.address
    assert event[0].newCustomProtocolFee == new_fee

    # Should now be different than default
    assert (
        vault_factory.protocolFeeConfig(sender=vault.address).feeRecipient
        == gov.address
    )
    assert vault_factory.protocolFeeConfig(sender=vault.address).feeBps == new_fee
    assert vault_factory.protocolFeeConfig(vault.address).feeRecipient == gov.address
    assert vault_factory.protocolFeeConfig(vault.address).feeBps == new_fee

    # Now remove the custom fee config
    tx = vault_factory.removeCustomProtocolFee(vault.address, sender=gov)

    event = list(tx.decode_logs(vault_factory.RemovedCustomProtocolFee))

    len(event) == 1
    assert event[0].vault == vault.address

    # Should now be the default
    assert (
        vault_factory.protocolFeeConfig(sender=vault.address).feeRecipient
        == gov.address
    )
    assert (
        vault_factory.protocolFeeConfig(sender=vault.address).feeBps == generic_fee
    )
    assert vault_factory.protocolFeeConfig(vault.address).feeRecipient == gov.address
    assert vault_factory.protocolFeeConfig(vault.address).feeBps == generic_fee

    assert vault_factory.useCustomProtocolFee(vault.address) == False
    assert vault_factory.customProtocolFee(vault.address) == 0


def test__set_protocol_fee_before_recipient__reverts(gov, vault_factory):
    assert vault_factory.protocolFeeConfig().feeRecipient == ZERO_ADDRESS

    with ape.reverts("no recipient"):
        vault_factory.setProtocolFeeBps(20, sender=gov)


def test__set_custom_fee_before_recipient__reverts(gov, vault_factory, vault):
    assert vault_factory.protocolFeeConfig().feeRecipient == ZERO_ADDRESS

    with ape.reverts("no recipient"):
        vault_factory.setCustomProtocolFeeBps(vault.address, 20, sender=gov)


def test__set_customProtocolFee_by_bunny__reverts(
    bunny, vault_factory, create_vault, asset
):
    vault = create_vault(asset, vault_name="new vault")
    with ape.reverts("not governance"):
        vault_factory.setCustomProtocolFeeBps(vault.address, 10, sender=bunny)


def test__set__customProtocolFees_too_high__reverts(
    gov, vault_factory, create_vault, asset
):
    vault = create_vault(asset, vault_name="new vault")
    with ape.reverts("fee too high"):
        vault_factory.setCustomProtocolFeeBps(vault.address, 5_001, sender=gov)


def test__removeCustomProtocolFee_by_bunny__reverts(
    bunny, vault_factory, create_vault, asset
):
    vault = create_vault(asset, vault_name="new vault")
    with ape.reverts("not governance"):
        vault_factory.removeCustomProtocolFee(vault, sender=bunny)


def test__setProtocolFeeRecipient_by_bunny__reverts(bunny, vault_factory):
    with ape.reverts("not governance"):
        vault_factory.setProtocolFeeRecipient(bunny.address, sender=bunny)


def test__set_protocolFees_too_high__reverts(gov, vault_factory):
    with ape.reverts("fee too high"):
        vault_factory.setProtocolFeeBps(10_001, sender=gov)


def test__set_protocolFees_by_bunny__reverts(bunny, vault_factory):
    with ape.reverts("not governance"):
        vault_factory.setProtocolFeeBps(20, sender=bunny)
