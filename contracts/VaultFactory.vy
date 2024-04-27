# @version 0.3.7

"""
@title Gefion Vault Factory
@license GNU AGPLv3
@author gefion.finance
@notice
    This vault Factory can be used by anyone wishing to deploy their own
    ERC4626 compliant Gefion Vault of the same API version.

    The factory clones new vaults from its specific `VAULT_ORIGINAL`
    immutable address set on creation of the factory.
    
    The deployments are done through create2 with a specific `salt` 
    that is derived from a combination of the deployer's address,
    the underlying asset used, as well as the name and symbol specified.
    Meaning a deployer will not be able to deploy the exact same vault
    twice and will need to use different name and or symbols for vaults
    that use the same other parameters such as `asset`.

    The factory also holds the protocol fee configs for each vault and strategy
    of its specific `API_VERSION` that determine how much of the fees
    charged are designated "protocol fees" and sent to the designated
    `feeRecipient`. The protocol fees work through a revenue share system,
    where if the vault or strategy decides to charge X amount of total
    fees during a `report` the protocol fees are a percent of X.
    The protocol fees will be sent to the designated feeRecipient and
    then (X - protocolFees) will be sent to the vault/strategy specific
    fee recipient.
"""

interface IVault:
    def initialize(
        asset: address, 
        name: String[64], 
        symbol: String[32], 
        roleManager: address, 
        profitMaxUnlockTime: uint256
    ): nonpayable

event NewVault:
    vaultAddress: indexed(address)
    asset: indexed(address)

event UpdateProtocolFeeBps:
    oldFeeBps: uint16
    newFeeBps: uint16

event UpdateProtocolFeeRecipient:
    oldFeeRecipient: indexed(address)
    newFeeRecipient: indexed(address)

event UpdateCustomProtocolFee:
    vault: indexed(address)
    newCustomProtocolFee: uint16

event RemovedCustomProtocolFee:
    vault: indexed(address)

event FactoryShutdown:
    pass

event UpdateGovernance:
    governance: indexed(address)

event NewPendingGovernance:
    pendingGovernance: indexed(address)

struct PFConfig:
    # Percent of protocol's split of fees in Basis Points.
    feeBps: uint16
    # Address the protocol fees get paid to.
    feeRecipient: address

# Identifier for this version of the vault.
API_VERSION: constant(String[28]) = "1.0.0"

# The max amount the protocol fee can be set to.
MAX_FEE_BPS: constant(uint16) = 5_000 # 50%

# The address that all newly deployed vaults are based from.
VAULT_ORIGINAL: immutable(address)

# State of the Factory. If True no new vaults can be deployed.
shutdown: public(bool)

# Address that can set or change the fee configs.
governance: public(address)
# Pending governance waiting to be accepted.
pendingGovernance: public(address)

# Name for identification.
name: public(String[64])

# The default config for assessing protocol fees.
defaultProtocolFeeConfig: public(PFConfig)
# Custom fee to charge for a specific vault or strategy.
customProtocolFee: public(HashMap[address, uint16])
# Represents if a custom protocol fee should be used.
useCustomProtocolFee: public(HashMap[address, bool])

@external
def __init__(name: String[64], vaultOriginal: address, governance: address):
    self.name = name
    VAULT_ORIGINAL = vaultOriginal
    self.governance = governance

@external
def deployNewVault(
    asset: address, 
    name: String[64], 
    symbol: String[32], 
    roleManager: address, 
    profitMaxUnlockTime: uint256
) -> address:
    """
    @notice Deploys a new clone of the original vault.
    @param asset The asset to be used for the vault.
    @param name The name of the new vault.
    @param symbol The symbol of the new vault.
    @param roleManager The address of the role manager.
    @param profitMaxUnlockTime The time over which the profits will unlock.
    @return The address of the new vault.
    """
    # Make sure the factory is not shutdown.
    assert not self.shutdown, "shutdown"

    # Clone a new version of the vault using create2.
    vaultAddress: address = create_minimal_proxy_to(
            VAULT_ORIGINAL, 
            value=0,
            salt=keccak256(_abi_encode(msg.sender, asset, name, symbol))
        )

    IVault(vaultAddress).initialize(
        asset, 
        name, 
        symbol, 
        roleManager, 
        profitMaxUnlockTime, 
    )
        
    log NewVault(vaultAddress, asset)
    return vaultAddress

@view
@external
def vaultOriginal()-> address:
    """
    @notice Get the address of the vault to clone from
    @return The address of the original vault.
    """
    return VAULT_ORIGINAL

@view
@external
def apiVersion() -> String[28]:
    """
    @notice Get the API version of the factory.
    @return The API version of the factory.
    """
    return API_VERSION

@view
@external
def protocolFeeConfig(vault: address = msg.sender) -> PFConfig:
    """
    @notice Called during vault and strategy reports 
    to retrieve the protocol fee to charge and address
    to receive the fees.
    @param vault Address of the vault that would be reporting.
    @return The protocol fee config for the msg sender.
    """
    # If there is a custom protocol fee set we return it.
    if self.useCustomProtocolFee[vault]:
        # Always use the default fee recipient even with custom fees.
        return PFConfig({
            feeBps: self.customProtocolFee[vault],
            feeRecipient: self.defaultProtocolFeeConfig.feeRecipient
        })
    else:
        # Otherwise return the default config.
        return self.defaultProtocolFeeConfig

@external
def setProtocolFeeBps(newProtocolFeeBps: uint16):
    """
    @notice Set the protocol fee in basis points
    @dev Must be below the max allowed fee, and a default
    feeRecipient must be set so we don't issue fees to the 0 address.
    @param newProtocolFeeBps The new protocol fee in basis points
    """
    assert msg.sender == self.governance, "not governance"
    assert newProtocolFeeBps <= MAX_FEE_BPS, "fee too high"

    # Cache the current default protocol fee.
    defaultConfig: PFConfig = self.defaultProtocolFeeConfig
    assert defaultConfig.feeRecipient != empty(address), "no recipient"

    # Set the new fee
    self.defaultProtocolFeeConfig.feeBps = newProtocolFeeBps

    log UpdateProtocolFeeBps(
        defaultConfig.feeBps, 
        newProtocolFeeBps
    )


@external
def setProtocolFeeRecipient(newProtocolFeeRecipient: address):
    """
    @notice Set the protocol fee recipient
    @dev Can never be set to 0 to avoid issuing fees to the 0 address.
    @param newProtocolFeeRecipient The new protocol fee recipient
    """
    assert msg.sender == self.governance, "not governance"
    assert newProtocolFeeRecipient != empty(address), "zero address"

    oldRecipient: address = self.defaultProtocolFeeConfig.feeRecipient

    self.defaultProtocolFeeConfig.feeRecipient = newProtocolFeeRecipient

    log UpdateProtocolFeeRecipient(
        oldRecipient,
        newProtocolFeeRecipient
    )
    

@external
def setCustomProtocolFeeBps(vault: address, newCustomProtocolFee: uint16):
    """
    @notice Allows Governance to set custom protocol fees
    for a specific vault or strategy.
    @dev Must be below the max allowed fee, and a default
    feeRecipient must be set so we don't issue fees to the 0 address.
    @param vault The address of the vault or strategy to customize.
    @param newCustomProtocolFee The custom protocol fee in BPS.
    """
    assert msg.sender == self.governance, "not governance"
    assert newCustomProtocolFee <= MAX_FEE_BPS, "fee too high"
    assert self.defaultProtocolFeeConfig.feeRecipient != empty(address), "no recipient"

    self.customProtocolFee[vault] = newCustomProtocolFee

    # If this is the first time a custom fee is set for this vault
    # set the bool indicator so it returns the correct fee.
    if not self.useCustomProtocolFee[vault]:
        self.useCustomProtocolFee[vault] = True

    log UpdateCustomProtocolFee(vault, newCustomProtocolFee)

@external 
def removeCustomProtocolFee(vault: address):
    """
    @notice Allows governance to remove a previously set
    custom protocol fee.
    @param vault The address of the vault or strategy to
    remove the custom fee for.
    """
    assert msg.sender == self.governance, "not governance"

    # Reset the custom fee to 0.
    self.customProtocolFee[vault] = 0

    # Set custom fee bool back to false.
    self.useCustomProtocolFee[vault] = False

    log RemovedCustomProtocolFee(vault)

@external
def shutdownFactory():
    """
    @notice To stop new deployments through this factory.
    @dev A one time switch available for governance to stop
    new vaults from being deployed through the factory.
    NOTE: This will have no effect on any previously deployed
    vaults that deployed from this factory.
    """
    assert msg.sender == self.governance, "not governance"
    assert self.shutdown == False, "shutdown"

    self.shutdown = True
    
    log FactoryShutdown()

@external
def setGovernance(newGovernance: address):
    """
    @notice Set the governance address
    @param newGovernance The new governance address
    """
    assert msg.sender == self.governance, "not governance"
    self.pendingGovernance = newGovernance

    log NewPendingGovernance(newGovernance)

@external
def acceptGovernance():
    """
    @notice Accept the governance address
    """
    assert msg.sender == self.pendingGovernance, "not pending governance"
    self.governance = msg.sender
    self.pendingGovernance = empty(address)

    log UpdateGovernance(msg.sender)

